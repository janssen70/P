'use strict';

let error_msg = null;

function success_callback(target_id)
{
}

function error_callback(error_code, error_reason)
{
   error_msg.html(`An error occurred. Code: {error_code}. Reason: {error_reason}`)
}

$(document).ready(function()
{
   let err_msg = $('#error');
   let c = $('#device_list');
   let org_id = c.attr('data-org');
   let service_id = c.attr('data-service');
   let client_id = c.attr('data-client');

   const webrtc = new WebRTCClient(org_id, client_id, 'remoteVideo', success_callbak, error_callback);

   $('.cam-button').click(function()
   {
      let mac = $(this).attr('data-cam');
      error_msg.html('');
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
