from threading import Thread
from flask import current_app, render_template
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def send_async_email(app, msg):
    with app.app_context():
        try:
            server = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
            if app.config['MAIL_USE_TLS']:
                server.starttls()
            server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
            server.send_message(msg)
            server.quit()
            print("Email sent successfully!")
        except Exception as e:
            print(f"Failed to send email: {e}")

def send_email(to, subject, template_prefix, **kwargs):
    app = current_app._get_current_object()

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"ADA Project <{app.config['MAIL_USERNAME']}>"
    msg['To'] = to

    # Render and attach both plain text and HTML parts
    text_body = render_template(template_prefix + '.txt', **kwargs)
    html_body = render_template(template_prefix + '.html', **kwargs)

    part1 = MIMEText(text_body, 'plain')
    part2 = MIMEText(html_body, 'html')

    msg.attach(part1)
    msg.attach(part2)

    # Send email in a background thread
    thr = Thread(target=send_async_email, args=[app, msg])
    thr.start()
    return thr
