/*
 * Add a message to a container element called 'message-area'
 *
 * Success messages auto-disappear
 */

function showMessage(type, message, autoDismiss = false)
{
   const area = document.getElementById('message-area');

   const banner = document.createElement('div');
   banner.className = 'message-banner ' + type;

   const text = document.createElement('span');
   text.textContent = message;

   const closeBtn = document.createElement('button');
   closeBtn.className = 'message-close';
   closeBtn.title = 'Dismiss';
   closeBtn.textContent = '×';
   closeBtn.onclick = () => banner.remove();

   banner.appendChild(text);
   banner.appendChild(closeBtn);
   area.appendChild(banner);

   if (autoDismiss) {
      setTimeout(() => banner.remove(), 10000);
   }
}

function showError(message)   { showMessage('error',   message); }
function showWarning(message) { showMessage('warning', message); }
function showSuccess(message) { showMessage('success', message, true); }

/* vim: set nowrap sw=3 sts=3 et fdm=marker: */
