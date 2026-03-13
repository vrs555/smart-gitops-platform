# gitops-controller/notifier.py
"""
Notifier Module
Sends alerts via Slack webhooks and email
when important events occur.
"""
import requests
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from config import Config

logger = logging.getLogger('gitops.notifier')


class Notifier:
    def __init__(self):
        self.slack_webhook = Config.SLACK_WEBHOOK_URL
        self.email_enabled = Config.EMAIL_ENABLED
        self.notification_history = []
        
    def send_slack(self, message, severity='info'):
        """Send a Slack notification."""
        if not self.slack_webhook:
            logger.debug("Slack webhook not configured, skipping")
            return False
        
        # Color based on severity
        colors = {
            'info': '#36a64f',      # Green
            'warning': '#ff9900',   # Orange
            'critical': '#ff0000',  # Red
            'success': '#36a64f',   # Green
            'rollback': '#ff6600'   # Dark Orange
        }
        
        # Emoji based on severity
        emojis = {
            'info': 'ℹ️',
            'warning': '⚠️',
            'critical': '🚨',
            'success': '✅',
            'rollback': '🔄'
        }
        
        payload = {
            'attachments': [{
                'color': colors.get(severity, '#36a64f'),
                'title': f"{emojis.get(severity, '')} GitOps Alert - {severity.upper()}",
                'text': message,
                'footer': 'Smart GitOps Platform',
                'ts': int(datetime.now().timestamp())
            }]
        }
        
        try:
            response = requests.post(
                self.slack_webhook, json=payload, timeout=10
            )
            if response.status_code == 200:
                logger.info(f"Slack notification sent: {severity}")
                self._record_notification('slack', severity, message, True)
                return True
            else:
                logger.error(
                    f"Slack notification failed: {response.status_code}"
                )
                self._record_notification('slack', severity, message, False)
                return False
        except Exception as e:
            logger.error(f"Slack notification error: {e}")
            self._record_notification('slack', severity, message, False)
            return False

    def send_email(self, subject, body):
        """Send an email notification."""
        if not self.email_enabled:
            logger.debug("Email notifications not enabled")
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = Config.SMTP_USER
            msg['To'] = Config.ALERT_EMAIL
            msg['Subject'] = f"[GitOps Alert] {subject}"
            
            html_body = f"""
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #333;">Smart GitOps Platform Alert</h2>
                <div style="background: #f5f5f5; padding: 15px; border-radius: 5px;">
                    {body}
                </div>
                <p style="color: #666; font-size: 12px;">
                    Generated at {datetime.now().isoformat()}
                </p>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(html_body, 'html'))
            
            with smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT) as server:
                server.starttls()
                server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
                server.send_message(msg)
            
            logger.info(f"Email notification sent: {subject}")
            self._record_notification('email', 'info', subject, True)
            return True
            
        except Exception as e:
            logger.error(f"Email notification error: {e}")
            self._record_notification('email', 'info', subject, False)
            return False

    def notify_deployment(self, commit, status, details=''):
        """Notify about a new deployment."""
        message = (
            f"*New Deployment*\n"
            f"• Commit: `{commit}`\n"
            f"• Status: {status}\n"
            f"• Details: {details}\n"
            f"• Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        self.send_slack(message, 'info')

    def notify_anomaly(self, metrics, ai_result):
        """Notify about detected anomaly."""
        message = (
            f"*Anomaly Detected!*\n"
            f"• Method: {ai_result.get('method', 'unknown')}\n"
            f"• Anomaly Score: {ai_result.get('anomaly_score', 'N/A')}\n"
            f"• Error Rate: {metrics.get('error_rate', 0)}%\n"
            f"• Response Time: {metrics.get('response_time', 0)}s\n"
            f"• CPU Usage: {metrics.get('cpu_usage', 0)}%\n"
            f"• Memory Usage: {metrics.get('memory_usage', 0)}%"
        )
        self.send_slack(message, 'critical')

    def notify_rollback(self, rollback_result):
        """Notify about a rollback event."""
        details = rollback_result.get('details', {})
        success = rollback_result.get('success', False)
        
        message = (
            f"*{'Rollback Successful' if success else 'Rollback Failed'}*\n"
            f"• Deployment: {details.get('deployment', 'unknown')}\n"
            f"• Reason: {details.get('reason', 'unknown')}\n"
            f"• From Revision: {details.get('from_revision', 'N/A')}\n"
            f"• To Revision: {details.get('to_revision', 'N/A')}\n"
            f"• Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        self.send_slack(
            message, 
            'success' if success else 'critical'
        )

    def notify_health_change(self, old_status, new_status, details=''):
        """Notify about health status change."""
        message = (
            f"*Health Status Changed*\n"
            f"• Previous: {old_status}\n"
            f"• Current: {new_status}\n"
            f"• Details: {details}"
        )
        severity = 'critical' if new_status == 'CRITICAL' else 'warning'
        self.send_slack(message, severity)

    def _record_notification(self, channel, severity, message, success):
        """Record notification in history."""
        self.notification_history.append({
            'timestamp': datetime.now().isoformat(),
            'channel': channel,
            'severity': severity,
            'message': message[:100],
            'success': success
        })
        self.notification_history = self.notification_history[-50:]

    def get_notification_history(self):
        """Get notification history."""
        return self.notification_history