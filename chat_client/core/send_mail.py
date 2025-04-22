import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from data.config import ConfigSMTP
import logging

logger: logging.Logger = logging.getLogger(__name__)


async def send_smtp_message(to_email, subject, plain_message, html_message=None, debug=False):
    logger.debug(f"SMTP Host: {ConfigSMTP.HOST}, Port: {ConfigSMTP.PORT}")

    try:
        # Create a secure SSL context
        context = ssl.create_default_context()

        # Connect to the server using smtplib.SMTP and then upgrade to TLS
        with smtplib.SMTP(ConfigSMTP.HOST, ConfigSMTP.PORT) as server:
            if debug:
                server.set_debuglevel(1)  # Enable debugging output
            server.ehlo()  # Can be omitted
            server.starttls(context=context)  # Secure the connection
            server.ehlo()  # Can be omitted
            server.login(ConfigSMTP.USERNAME, ConfigSMTP.PASSWORD)

            # Prepare the email
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = ConfigSMTP.DEFAULT_FROM
            msg["To"] = to_email

            # Attach the message body
            part1 = MIMEText(plain_message, "plain")
            msg.attach(part1)

            if html_message:
                part2 = MIMEText(html_message, "html")
                msg.attach(part2)

            # Send the email
            server.sendmail(
                ConfigSMTP.USERNAME,
                to_email,
                msg.as_string(),
            )
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise
