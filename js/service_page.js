
$(document).ready(function()
{
	let org_id = $('#device_list').attr('data-org');
	let service_id = $('#device_list').attr('data-service');
	console.log(org_id);

	const webrtc = new WebRTCClient(org_id, 'remoteVideo');

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
