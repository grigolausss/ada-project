# app/utils/email.py
from threading import Thread
from flask import current_app, render_template
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def _deliver_with_smtp(app, msg):
    """Invia il messaggio via SMTP rispettando TLS/SSL. Ritorna True/False."""
    cfg = app.config
    host = cfg.get('MAIL_SERVER')
    port = int(cfg.get('MAIL_PORT') or 0)
    use_tls = bool(cfg.get('MAIL_USE_TLS'))
    use_ssl = bool(cfg.get('MAIL_USE_SSL'))
    username = cfg.get('MAIL_USERNAME')
    password = cfg.get('MAIL_PASSWORD')

    # Validazione minima
    if not host or not port:
        app.logger.warning("MAIL non configurata: server/port mancanti. Stampo in console.")
        print("=== EMAIL (FAKE SEND) ===")
        print(msg.as_string())
        print("=========================")
        return True

    # Se mancano le credenziali, tenta comunque l'invio se il server lo consente,
    # altrimenti fai fallback “stampa in console” per dev.
    if not username or not password:
        app.logger.warning("MAIL non configurata: username/password mancanti. Stampo in console.")
        print("=== EMAIL (FAKE SEND) ===")
        print(msg.as_string())
        print("=========================")
        return True

    try:
        timeout = 15
        if use_ssl:
            server = smtplib.SMTP_SSL(host=host, port=port, timeout=timeout)
        else:
            server = smtplib.SMTP(host=host, port=port, timeout=timeout)

        try:
            server.ehlo()
            if use_tls and not use_ssl:
                server.starttls()
                server.ehlo()

            server.login(username, password)
            server.send_message(msg)
        finally:
            try:
                server.quit()
            except Exception:
                server.close()

        app.logger.info("Email inviata con successo a %s", msg['To'])
        return True

    except smtplib.SMTPAuthenticationError as e:
        app.logger.error("Autenticazione SMTP fallita: %s", e)
        return False
    except Exception as e:
        app.logger.error("Errore invio email: %s", e)
        return False


def _send_async(app, msg):
    with app.app_context():
        _deliver_with_smtp(app, msg)


def send_email(to, subject, template_prefix, **kwargs):
    """
    Invia email in background. Se la config mail è assente, stampa in console e ritorna True.
    template_prefix: base del template senza estensione (usa .txt e .html)
    """
    app = current_app._get_current_object()
    cfg = app.config

    default_sender = cfg.get('MAIL_DEFAULT_SENDER')
    username = cfg.get('MAIL_USERNAME')

    sender = default_sender or (f"ADA Project <{username}>" if username else None)

    # Se proprio non abbiamo un sender, fallback brutale e non crashare.
    if not sender:
        app.logger.warning("MAIL_DEFAULT_SENDER e MAIL_USERNAME assenti. Stampo in console.")
        text_body = render_template(template_prefix + '.txt', **kwargs)
        html_body = render_template(template_prefix + '.html', **kwargs)
        print("=== EMAIL (FAKE SEND) ===")
        print(f"To: {to}")
        print(f"Subject: {subject}")
        print(text_body)
        print(html_body)
        print("=========================")
        return True

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = to

    # Render parti testo + HTML
    text_body = render_template(template_prefix + '.txt', **kwargs)
    html_body = render_template(template_prefix + '.html', **kwargs)

    msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    # Thread di invio
    thr = Thread(target=_send_async, args=(app, msg), daemon=True)
    thr.start()
    return True