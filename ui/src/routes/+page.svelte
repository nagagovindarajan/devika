<script>
  import { onDestroy, onMount } from "svelte";
  import { toast } from "svelte-sonner";
  import { chart } from "svelte-apexcharts";

  import ControlPanel from "$lib/components/ControlPanel.svelte";
  import MessageContainer from "$lib/components/MessageContainer.svelte";
  import MessageInput from "$lib/components/MessageInput.svelte";
  import BrowserWidget from "$lib/components/BrowserWidget.svelte";
  import TerminalWidget from "$lib/components/TerminalWidget.svelte";
  import EditorWidget from "../lib/components/EditorWidget.svelte";
  import * as Resizable from "$lib/components/ui/resizable/index.js";
  import * as Tabs from "$lib/components/ui/tabs";
  import Seperator from "$lib/components/ui/Seperator.svelte";

  import { serverStatus, selectedTab, graphicsData } from "$lib/store";
  import { initializeSockets, destroySockets } from "$lib/sockets";
  import { checkInternetStatus, checkServerStatus } from "$lib/api";
  import { generatePieChartOptions, generateBarChartOptions, generateTimeSeriesChartOptions } from "$lib/utils";

  let resizeEnabled =
    localStorage.getItem("resize") &&
    localStorage.getItem("resize") === "enable";

  onMount(() => {
    const load = async () => {
      await checkInternetStatus();

      if(!(await checkServerStatus())) {
        toast.error("Failed to connect to server");
        return;
      }
      serverStatus.set(true);
      await initializeSockets();
    };
    load();
  });
  onDestroy(() => {
    destroySockets();
  });
  selectedTab.set('browser');
</script>

<div class="flex h-full flex-col flex-1 gap-4 p-4 overflow-hidden">
  <ControlPanel />

  <div class="flex h-full overflow-x-scroll">
    <div class="flex flex-1 min-w-[calc(100vw-120px)] h-full gap-2">
      <div class="flex flex-col gap-2 w-full h-full pr-4">
        <MessageContainer />
        <MessageInput />
      </div>
      <div class="flex flex-col gap-4 h-full w-full p-2">
        <Tabs.Root
          value="{$selectedTab}"
          class="h-full w-full p-2 flex flex-col justify-start ms-2">
          <Tabs.List class="ps-0">
            <Tabs.Trigger value="terminal">Terminal</Tabs.Trigger>
            <Tabs.Trigger value="browser">Browser</Tabs.Trigger>
            <Tabs.Trigger value="editor">Editor</Tabs.Trigger>
            <Tabs.Trigger value="graphics">Graphics</Tabs.Trigger>
          </Tabs.List>
          
          <Seperator direction="vertical"/>

          <Tabs.Content value="terminal" class="gap-4 h-full w-full p-2 mt-4">
            <TerminalWidget />
          </Tabs.Content>
          <Tabs.Content value="browser" class="gap-4 h-full w-full p-2 mt-4">
            <BrowserWidget />
          </Tabs.Content>
          <Tabs.Content value="editor" class="gap-4 h-full w-full p-2 mt-4">
            <EditorWidget />
          </Tabs.Content>
          <Tabs.Content value="graphics" class="gap-4 h-full w-full p-2 mt-4">
            <div class="w-full h-full flex flex-col border-[3px] rounded-xl overflow-y-auto border-window-outline content-center">
              {#if $graphicsData.type === "pie"}
                  <div class="chart" use:chart={generatePieChartOptions($graphicsData.message)} /> 
              {:else if $graphicsData.type === "bar"}
                  <div class="chart" use:chart={generateBarChartOptions($graphicsData.message)} /> 
              {:else if $graphicsData.type === "timeseries"}
                  <div class="chart" use:chart={generateTimeSeriesChartOptions($graphicsData.message)} /> 
              {/if}
            </div>
          </Tabs.Content>
        </Tabs.Root>
      </div>
    </div>
  </div>
</div>

<style>
  .chart {
    background-color: white;
  }
</style>