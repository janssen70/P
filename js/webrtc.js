// webrtc.js
// Handles WebRTC connection logic on the service_page

class WebRTCClient
{
   constructor(orgUuid, videoElementId)
   {
      this.orgUuid = orgUuid;
      this.videoElementId = videoElementId;
      this.clientId = 'cid_0EBA4F87';
      this._reset();
   }

   _reset()
   {
      this.pc = null;
      this.ws = null;
      this.sessionId = null;
      this.correlationId = null;
      this.token = null;
      this.targetId = null;
   }

   stop()
   {
      // TODO: Insert protocol-level session teardown message here once the
      // signaling protocol teardown procedure has been determined.
      if (this.ws)
      {
         this.ws.onmessage = null;
         this.ws.onerror = null;
         this.ws.onopen = null;
         this.ws.close();
      }
      if (this.pc)
      {
         this.pc.ontrack = null;
         this.pc.onicecandidate = null;
         this.pc.close();
      }
      const videoEl = document.getElementById(this.videoElementId);
      if (videoEl)
         videoEl.srcObject = null;
      this._reset();
   }

   async play(tokenInput, targetId)
   {
      this.stop();

      /*
       * This url relies on proxy forward with adjusted headers
       */
      const wsBaseUrl = 'wss://' + window.location.host + '/prod-signal/client';
      this.token = `Bearer ${tokenInput.trim()}`;
      this.targetId = targetId;

      if (!this.token || !this.targetId)
      {
         console.error("Missing required parameters for WebRTC connection.");
         return;
      }

      this.sessionId = String(Math.floor(Math.random() * 1e8));
      this.correlationId = crypto.randomUUID();

      try
      {
         const wsUrl = `${wsBaseUrl}?authorization=Bearer ${tokenInput.trim()}`;
         this.ws = new WebSocket(wsUrl, []);
      }
      catch (error)
      {
         console.error("WebSocket connection error:", error);
         return;
      }

      this.ws.onopen = () =>
      {
         console.log("WebSocket connected.");
         this.ws.send(JSON.stringify({ type: "hello", id: "" }));
      };

      this.ws.onmessage = async (message) =>
      {
         const data = JSON.parse(message.data);
         console.log('Got:');
         console.log(data);

         if (data.type === "hello" && data.id)
         {
            const initMsg = {
               type: "initSession",
               targetId: this.targetId,
               orgId: this.orgUuid,
               clientId: this.clientId,
               authorization: this.token,
               correlationId: this.correlationId,
               data: {
                  apiVersion: "1.0",
                  type: "request",
                  sessionId: this.sessionId,
                  method: "initSession",
                  params: {
                     type: "live",
                     videoReceive: {
                        width: 640,
                        height: 480,
                        framerate: 15,
                        channel: 1,
                        codecPreference: ['AV1', 'H264']
                     },
                     audioReceive: {
                     }
                  }
               }
            };
            console.log('initSession: ' + initMsg);
            this.ws.send(JSON.stringify(initMsg));
         }

         if (data.type === "initSession" && data.data?.method === "initSession")
         {
            let iceServers = [];
            if (Array.isArray(data.turnServers))
            {
               data.turnServers.forEach(s =>
                  {
                     iceServers.push({ urls: s.urls, username: s.username, credential: s.password });
                  });
            }
            if (Array.isArray(data.stunServers))
            {
               data.stunServers.forEach(s =>
                  {
                     iceServers.push({ urls: s.urls });
                  });
            }
            if (!this.pc)
            {
               this.pc = new RTCPeerConnection({ iceServers });
               this.pc.ontrack = (event) =>
               {
                  console.log('Set ' + this.videoElementId + ' element');
                  document.getElementById(this.videoElementId).srcObject = event.streams[0];
               };
               this.pc.onicecandidate = (event) =>
               {
                  console.log('In onicecandidate callback');
                  if (event.candidate && this.sessionId)
                  {
                     console.log('Sending ICE Candidate request');
                     const iceMsg = {
                        type: "signaling",
                        targetId: this.targetId,
                        orgId: this.orgUuid,
                        clientId: this.clientId,
                        authorization: this.token,
                        correlationId: this.correlationId,
                        data: {
                           apiVersion: "1.0",
                           sessionId: this.sessionId,
                           method: "addIceCandidate",
                           type: "request",
                           params: {
                              candidate: event.candidate.candidate,
                              sdpMLineIndex: event.candidate.sdpMLineIndex
                           },
                           context: String(Date.now())
                        }
                     };
                     console.log(JSON.stringify(iceMsg));
                     this.ws.send(JSON.stringify(iceMsg));
                  }
               };
            }
         }

         if (data.type === "signaling" && data.data?.method === "initSession" && data.data?.type === "response")
         {
            console.log('Wait for setSdpOffer');
         }

         if (data.type === "signaling" && data.data?.method === "setSdpOffer")
         {
            const offerSDP = data.data.params.sdp;
            console.log('Got:');
            console.log(offerSDP);
            await this.pc.setRemoteDescription(new RTCSessionDescription({ type: "offer", sdp: offerSDP }));
            this.ws.send(JSON.stringify({
               type: "signaling",
               targetId: this.targetId,
               orgId: this.orgUuid,
               clientId: this.clientId,
               authorization: this.token,
               correlationId: this.correlationId,
               data: {
                  apiVersion: "1.0",
                  method: "setSdpOffer",
                  type: "response",
                  sessionId: this.sessionId,
                  id: "1",
                  data: {}
               }
            }));
            const answer = await this.pc.createAnswer();
            await this.pc.setLocalDescription(answer);
            console.log('Answering:');
            console.log(answer.sdp);
            this.ws.send(JSON.stringify({
               type: "signaling",
               targetId: this.targetId,
               orgId: this.orgUuid,
               clientId: this.clientId,
               authorization: this.token,
               correlationId: this.correlationId,
               data: {
                  apiVersion: "1.0",
                  sessionId: this.sessionId,
                  type: "request",
                  method: "setSdpAnswer",
                  params: {
                     type: "answer",
                     sdp: answer.sdp
                  }
               }
            }));
         }

         if (data.type === "signaling" && data.data?.method === "setSdpAnswer" && data.data?.type === "response")
         {
            console.log('Received SDP answer acknowledgement');
         }

         if (data.type === "signaling" && data.data?.method === "addIceCandidate" && data.data?.type === "request")
         {
            const candidate = new RTCIceCandidate(data.data.params);
            await this.pc.addIceCandidate(candidate);
            this.ws.send(JSON.stringify({
               type: "signaling",
               targetId: this.targetId,
               orgId: this.orgUuid,
               clientId: this.clientId,
               authorization: this.token,
               correlationId: this.correlationId,
               data: {
                  apiVersion: "1.0",
                  method: "addIceCandidate",
                  type: "response",
                  sessionId: this.sessionId,
                  context: data.data.context,
                  id: String(Date.now()),
                  data: {}
               }
            }));
         }

         if (data.type === "signaling" && data.data?.method === "addIceCandidate" && data.data?.type === "response")
         {
            console.log('Received ICE candidate acknowledgement');
         }
      };

      this.ws.onerror = (err) => console.error("WebSocket error:", err);
   }
}

/* vim: set nowrap sw=3 sts=3 et fdm=marker: */
