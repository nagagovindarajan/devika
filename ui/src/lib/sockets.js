import { socket } from "./api";
import { messages, agentState, isSending, tokenUsage, selectedTab, graphicsData } from "./store";
import { toast } from "svelte-sonner";
import { get } from "svelte/store";

let prevMonologue = null;
const graphicsTypes = ["pie", "bar", "timeseries"]

export function initializeSockets() {

  socket.connect();
  
  let state = get(agentState);
  prevMonologue = state?.internal_monologue;

  socket.emit("socket_connect", { data: "frontend connected!" });
  socket.on("socket_response", function (msg) {
    console.log(msg);
  });

  socket.on("server-message", function (data) {
    console.log("message received:", data);
    if (graphicsTypes.includes(data["messages"].type)){
      selectedTab.set('graphics');
      graphicsData.set(data["messages"]);
    }
    messages.update((msgs) => [...msgs, data["messages"]]);
  });

  socket.on("agent-state", function (state) {
    const lastState = state[state.length - 1];
    agentState.set(lastState);
    if (lastState.completed) {
      isSending.set(false);
    }
    if(lastState.browser_session && lastState.browser_session.url && lastState.browser_session.url.length > 0){
      selectedTab.set('browser');
    } else if(lastState.terminal_session && lastState.command && lastState.command.length > 0){
      selectedTab.set('terminal');
    } 
    // else {
    //   selectedTab.set('graphics');
    // }
    console.log("current state ", lastState);
  });

  socket.on("tokens", function (tokens) {
    tokenUsage.set(tokens["token_usage"]);
  });

  socket.on("inference", function (error) {
    if (error["type"] == "error") {
      toast.error(error["message"]);
      isSending.set(false);
    } else if (error["type"] == "warning") {
      toast.warning(error["message"]);
    }
  });

  socket.on("info", function (info) {
    if (info["type"] == "error") {
      toast.error(info["message"]);
      isSending.set(false);
    } else if (info["type"] == "warning") {
      toast.warning(info["message"]);
    } else if (info["type"] == "info") {
      toast.info(info["message"]);
    }
  });

  
  agentState.subscribe((state) => {
    function handleMonologueChange(newValue) {
      if (newValue) {
        toast(newValue);
      }
    }
    if (
      state &&
      state.internal_monologue &&
      state.internal_monologue !== prevMonologue
    ) {
      handleMonologueChange(state.internal_monologue);
      prevMonologue = state.internal_monologue;
    }
  });
}

export function destroySockets() {
  if (socket.connected) {
    socket.off("socket_response");
    socket.off("server-message");
    socket.off("agent-state");
    socket.off("tokens");
    socket.off("inference");
    socket.off("info");
  }
}

export function emitMessage(channel, message) {
  socket.emit(channel, message);
}

export function socketListener(channel, callback) {
  socket.on(channel, callback);
}
