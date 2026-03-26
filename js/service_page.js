'use strict';

function success_callback(target_id)
{
   showSuccess(`Connected to ${target_id}`);
}

function error_callback(error_code, error_reason)
{
   showError(`An error occurred. Code: ${error_code}. Reason: ${error_reason}`)
}

$(document).ready(function()
{
   let c = $('#device_list');
   let org_id = c.attr('data-org');
   let service_id = c.attr('data-service');
   let client_id = c.attr('data-client');

   const webrtc = new WebRTCClient(org_id, client_id, 'remoteVideo', success_callback, error_callback);

   $('.cam-button').click(function()
   {
      let mac = $(this).attr('data-cam');
      $.ajax({
         method: 'GET',
         url: Urls.p_service_token(service_id)
      })
      .done(function(token)
      {
         console.log(mac);
         webrtc.play(token, mac);
      });
   });
});

/* vim: set nowrap sw=3 sts=3 et fdm=marker: */
