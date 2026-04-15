'use strict';

let rec_table = null;
let current_mac = null;

function show_processing()
{
   document.body.style.cursor = 'wait';
   $('#search_form_submit').addClass('pure-button-disabled');
}

function show_ready()
{
   document.body.style.cursor = 'default';
   $('#search_form_submit').removeClass('pure-button-disabled');
}

function success_callback(target_id)
{
   showSuccess(`Connected to ${target_id}`);
}

function error_callback(error_code, error_reason)
{
   showError(`An error occurred. Code: ${error_code}. Reason: ${error_reason}`)
}

function preprocess_recordings(data)
{
   for (let i = 0; i < data.length; ++i)
   {
      let start = new Date(data[i].starttime);
      let stop  = new Date(data[i].stoptime);
      data[i].duration = Math.round((stop - start) / 1000);
      data[i].starttime = start;
      data[i].stoptime = stop;
   }
   return data;
}

function register_recording_contextmenu(trigger_def, service_id)
{
   $.contextMenu({
      selector: trigger_def.selector,
      trigger: trigger_def.trigger,
      build: function($trigger, e)
      {
         var row = rec_table.row($trigger.parents('tr'));
         var data = row.data();
         return {
            callback: function(key, options) {},
            items: {
               'download': {
                  name: 'Download',
                  icon: 'fas fa-download',
                  disabled: false,
                  callback: function(itemKey, opt, e)
                  {
                     window.location = Urls.p_edgerecording_get(service_id, current_mac, data.diskid, data.recordingid);
                  }
               }
            }
         };
      }
   });
}

function add_handlers(service_id)
{
   rec_table.on('click touch', '.fa-ellipsis-v', function(ev)
   {
      ev.preventDefault();
      $(this).contextMenu();
   });

   [
      { selector: '#recordings_list .dt-left', trigger: 'right' },
      { selector: '#recordings_list .fa-ellipsis-v', trigger: 'none' }
   ].forEach(function(t, i, a)
   {
      register_recording_contextmenu(t, service_id);
   });
}

function create_recordings_table(elem, data)
{
   rec_table = elem.DataTable(
   {
      data: data,
      paging: true,
      ordering: true,
      order: [[2, 'desc']],
      language: getTableLanguage(),
      info: true,
      searching: false,
      autoWidth: false,
      columns: [
         { data: 'recordingid' },
         { data: 'recordingtype' },
         { data: 'starttime', render: date_formatter },
         { data: 'duration' },
         { data: 'recordingstatus' },
         { data: null, width: '2%', render: function(data, type, row)
            {
               return '<span class="fas fa-ellipsis-v click_icon"></span>';
            }
         }
      ],
      columnDefs: [
         { className: 'dt-left', targets: [0, 1, 2, 4] },
         { className: 'dt-center', targets: [3] },
         { orderable: false, targets: [5] }
      ]
   });
   return rec_table;
}

function create_or_update_recordings_table(elem, data, service_id)
{
   if (data.length === 0)
   {
      elem.addClass('hidden');
      return;
   }
   data = preprocess_recordings(data);
   console.log(data);
   elem.removeClass('hidden');
   if (rec_table === null)
   {
      create_recordings_table(elem, data);
      add_handlers(service_id);
   }
   else
   {
      rec_table.clear();
      rec_table.rows.add(data);
      rec_table.draw();
   }
}

function request_recordings(service_id, mac)
{
   $.ajax({
      method: 'GET',
      url: Urls.p_edgerecording_list_json(service_id, mac),
      dataType: 'json'
   })
   .done(function(response)
   {
      create_or_update_recordings_table($('#recordings_list'), response.data || [], service_id);
   });
}

$(document).ready(function()
{
   let c = $('#device_list');
   let org_id = c.attr('data-org');
   let service_id = c.attr('data-service');
   let client_id = c.attr('data-client');

   let error_msg = $('#error').attr('data-msg');
   if (error_msg != undefined)
   {
      showError('serverside_error', error_msg);
   }

   const webrtc = new WebRTCClient(org_id, client_id, 'remoteVideo', success_callback, error_callback);

   $('.cam-button').click(function()
   {
      let mac = $(this).attr('data-cam');
      current_mac = mac;
      /*
       * Start filling the edge recording table (if edge recordings exist)
       */
      request_recordings(service_id, mac);
      /*
       * Commence WebRTC
       */
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
