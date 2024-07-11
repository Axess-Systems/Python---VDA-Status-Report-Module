import os
import logging
import requests
from dotenv import load_dotenv
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Base URL for the API
base_url = "https://api.cloud.com"

def get_customer_details():
    customers = {}
    i = 1
    while True:
        customer_id = os.getenv(f'CUSTOMER_ID_{i}')
        if not customer_id:
            break
        customers[customer_id] = {
            'client_id': os.getenv(f'CLIENT_ID_{i}'),
            'client_secret': os.getenv(f'CLIENT_SECRET_{i}'),
            'customer_name': os.getenv(f'CUSTOMER_NAME_{i}'),
            'site_id': os.getenv(f'SITE_ID_{i}')
        }
        i += 1
    return customers

def get_vda_status(token, customer_id, site_id):
    url = f"{base_url}/cvad/manage/Machines"
    auth_token = f"CwsAuth bearer={token}"
    headers = {
        'Accept': 'application/json',
        'Citrix-CustomerId': customer_id,
        'Citrix-InstanceId': site_id,
        'Authorization': auth_token
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

def create_report(data):
    report = ""
    for customer_id, vda_data in data.items():
        client_name = customers[customer_id]['customer_name']
        report += f"<h2>Client Name: {client_name}</h2>"
        
        machine_catalogs = {}
        for item in vda_data['Items']:
            machine_catalog = item.get('MachineCatalog', {}).get('Name', 'Unknown')
            if machine_catalog not in machine_catalogs:
                machine_catalogs[machine_catalog] = []
            machine_catalogs[machine_catalog].append(item)
        
        for machine_catalog, items in machine_catalogs.items():
            report += f"<h3>MachineCatalog: {machine_catalog}</h3>"
            
            report += """
            <table border="1">
                <tr>
                    <th>MachineName</th>
                    <th>OSType</th>
                    <th>AllocationType</th>
                    <th>RegistrationState</th>
                    <th>SummaryState</th>
                    <th>SessionCount</th>
                    <th>Multisession</th>
                    <th>LastConnectionUser</th>
                    <th>LastConnectionTime</th>
                    <th>MaintenanceMode</th>
                </tr>
            """
            
            for item in items:
                machine_name = item.get('Name', '')
                os_type = item.get('OSType', '')
                allocation_type = item.get('AllocationType', '')
                registration_state = item.get('RegistrationState', '')
                summary_state = item.get('SummaryState', '')
                session_count = item.get('SessionCount', '')
                multisession = 'Yes' if item.get('SessionCount', 0) > 1 else 'No'
                last_connection_user = item.get('LastConnectionUser', {}).get('DisplayName', '')
                last_connection_time = item.get('FormattedLastConnectionTime', '')
                maintenance_mode = 'Yes' if item.get('InMaintenanceMode', False) else 'No'
                
                report += f"""
                <tr>
                    <td>{machine_name}</td>
                    <td>{os_type}</td>
                    <td>{allocation_type}</td>
                    <td>{registration_state}</td>
                    <td>{summary_state}</td>
                    <td>{session_count}</td>
                    <td>{multisession}</td>
                    <td>{last_connection_user}</td>
                    <td>{last_connection_time}</td>
                    <td>{maintenance_mode}</td>
                </tr>
                """
            
            report += "</table><br>"
    
    return report

def send_email(subject, body, recipients):
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = int(os.getenv('SMTP_PORT'))
    smtp_username = os.getenv('SMTP_USERNAME')
    smtp_password = os.getenv('SMTP_PASSWORD')
    use_tls = os.getenv('USE_TLS', 'False').lower() == 'true'

    msg = MIMEMultipart()
    msg['From'] = smtp_username
    msg['To'] = ', '.join(recipients)
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'html'))

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        if use_tls:
            server.starttls()
        server.login(smtp_username, smtp_password)
        server.send_message(msg)

def get_bearer_token(customer_id, client_id, client_secret):
    url = f"https://api.cloud.com/cctrustoauth2/{customer_id}/tokens/clients"
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    payload = {
        'grant_type': 'client_credentials',
        'client_id': client_id,
        'client_secret': client_secret
    }
    response = requests.post(url, headers=headers, data=payload)
    response.raise_for_status()
    return response.json().get('access_token')

def vda_status_task():
    logging.info(f"Running VDA status task for customers: {list(customers.keys())}")

    data = {}
    for customer_id, details in customers.items():
        try:
            token = get_bearer_token(customer_id, details['client_id'], details['client_secret'])
            data[customer_id] = get_vda_status(token, customer_id, details['site_id'])
        except Exception as e:
            logging.error(f"Failed to get VDA status for {customer_id}: {str(e)}")

    report = create_report(data)

    # Save the report to a text file
    with open('vda_status_report.html', 'w') as file:
        file.write(report)

    # Send email
    recipients = os.getenv('EMAIL_RECIPIENTS').split(',')
    subject = "VDA Status Report"
    send_email(subject, report, recipients)

    return report

if __name__ == "__main__":
    customers = get_customer_details()
    vda_status_task()