'use strict';

var table_elem = null;
var data_url = null;
var table = null;
var t = null;

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

function register_service_contextmenu(trigger_def)
{
   $.contextMenu({
      selector: trigger_def.selector,
      trigger: trigger_def.trigger,
      build: function($trigger, e)
      {
         var row = table.row($trigger.parents('tr'));
         var data = row.data();
         return {
            callback: function(key, options) {},
            items: {
               'consent': {
                  name: t['Consent'],
                  icon: 'fas fa-key',
                  disabled: false,
                  visible: !data.consent && !!data.consent_request_token,
                  callback: function(itemKey, opt, e)
                  {
                     window.location.href = Urls['p_oauth_start'](data.consent_request_token);
                  }
               },
               'sep0': '---------',
               'edit': {
                  name: t['Properties'],
                  icon: 'fas fa-pen-alt',
                  disabled: false,
                  callback: function(itemKey, opt, e)
                  {
                     doForm(
                        Urls.p_my_service_edit(data.id),
                        t['Properties'],
                        'serviceform',
                        600, 500, 400,
                        null,
                        function(response)
                        {
                           var updated = preprocess_data([response.data[0]])[0];
                           row.data(updated).draw(false);
                        }
                     );
                  }
               },
               'sep1': '---------',
               'revoke': {
                  name: t['Revoke'] + '...',
                  icon: 'fas fa-ban',
                  disabled: !data.consent,
                  callback: function(itemKey, opt, e)
                  {
                     doubleCheck(
                        t['Revoke'],
                        t['SureToRevoke'].format(data.description),
                        t['RevokeButton'],
                        function()
                        {
                           postUrl(
                              Urls.p_service_revoke(data.id),
                              'operation_result',
                              t['Processing'],
                              t['ConsentRevoked'],
                              [],
                              function(response)
                              {
                                 var updated = preprocess_data(response.data)[0];
                                 row.data(updated).draw(false);
                              }
                           );
                        }
                     );
                  }
               },
               'sep2': '---------',
               'delete': {
                  name: t['Delete'],
                  icon: 'fas fa-trash-alt',
                  disabled: false,
                  callback: function(itemKey, opt, e)
                  {
                     doubleCheck(
                        t['DeleteService'],
                        t['SureToDelete'].format(data.description),
                        t['DeleteButton'],
                        function()
                        {
                           postUrl(
                              Urls.p_service_rm(data.id),
                              'operation_result',
                              t['Processing'],
                              t['ServiceDeleted'],
                              [],
                              function()
                              {
                                 row.remove().draw();
                              }
                           );
                        }
                     );
                  }
               }
            }
         };
      }
   });
}

function add_service_handlers(my_table)
{
   my_table.on('click touch', '.fa-ellipsis-v', function(ev)
   {
      ev.preventDefault();
      $(this).contextMenu();
   });

   [
      { selector: '#service_list .dt-left', trigger: 'right' },
      { selector: '#service_list .dt-right', trigger: 'right' },
      { selector: '#service_list .fa-ellipsis-v', trigger: 'none' }
   ].forEach(function(t, i, a)
   {
      register_service_contextmenu(t);
   });
}

function create_table(elem, data)
{
   table = elem.DataTable(
   {
      data: data,
      paging: true,
      ordering: true,
      order: [[1, 'desc']],
      language: getTableLanguage(),
      info: true,
      searching: true,
      autoWidth: false,
      responsive: {
         details: false
      },
      columns: [
         { data: 'description' },
         { data: 'created_at', render: date_formatter },
         { data: 'consent', render: function(data, type, row)
            {
               return data ? t['Yes'] : t['No'];
            }
         },
         { data: null, width: '2%', render: function(data, type, row)
            {
               return '<span class="fas fa-ellipsis-v click_icon"></span>';
            }
         }
      ],
      createdRow: function(row, data, dataIndex)
      {
         if (!data.consent)
         {
            $(row).addClass('no-consent-row');
         }
      },
      columnDefs: [
         { className: 'dt-left', targets: [0, 2] },
         { className: 'dt-right', targets: [1] },
         { className: 'dt-center', targets: [3] },
         { orderable: false, targets: [3] }
      ]
   });

   add_service_handlers(table);
   return table;
}

function preprocess_data(response)
{
   for (let i = 0; i < response.length; ++i)
   {
      if (response[i].created_at != null)
      {
         response[i].created_at = new Date(response[i].created_at);
      }
   }
   return response;
}

function create_or_update_table(the_container, response)
{
   response = preprocess_data(response);
   if (table == null)
   {
      the_container.removeClass('hidden');
      table = create_table(the_container, response);
   }
   else
   {
      table.clear();
      table.rows.add(response);
      table.draw();
   }
}

function request_services(the_container, url)
{
   show_processing();
   $.ajax({
      method: 'GET',
      url: url,
      data: $('#search_form').serialize(),
      dataType: 'json'
   })
   .done(function(response)
   {
      dynamic_error_or_callback(
         response,
         'search_form_result',
         function(results)
         {
            create_or_update_table(the_container, results);
         }
      );
   })
   .fail(function()
   {
      _errorMsg($('#search_form_result'), t['ErrorSearching']);
   })
   .always(function()
   {
      show_ready();
   });
}

function handleVisibilityChange()
{
   if (document.visibilityState == 'visible')
   {
      if (table != null)
      {
         request_services(table_elem, data_url);
      }
   }
}

$(document).ready(function()
{
   t = JSON.parse($('#translations').html());

   table_elem = $('#service_list');
   data_url = table_elem.attr('data-url');

   request_services(table_elem, data_url);

   $('#add_service').click(function()
   {
      doForm(
         $(this).attr('data-url'),
         t['AddService'],
         'serviceform',
         600, 500, 400,
         null,
         function(response)
         {
            var new_row = preprocess_data([response.data[0]])[0];
            if (table == null)
            {
               create_or_update_table(table_elem, [new_row]);
            }
            else
            {
               table.row.add(new_row).draw();
            }
         }
      );
   });

   $('#search_form').submit(function()
   {
      request_services(table_elem, data_url);
      return false;
   });

   document.addEventListener('visibilitychange', handleVisibilityChange, false);
});

/* vim: set nowrap sw=3 sts=3 et fdm=marker: */
