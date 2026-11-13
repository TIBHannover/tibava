import Vue from "vue";
import axios from "../plugins/axios";
import config from "../../app.config";

import { defineStore } from "pinia";
import { usePlayerStore } from "./player";
import { useAnnotationStore } from "./annotation";
import { useShortcutStore } from "./shortcut";
import { useAnnotationShortcutStore } from "./annotation_shortcut";
import { useAnnotationCategoryStore } from "./annotation_category";
import { useTimelineStore } from "./timeline";
import { useTimelineSegmentStore } from "./timeline_segment";
import { useTimelineSegmentAnnotationStore } from "./timeline_segment_annotation";

import { usePluginStore } from "./plugin";
import { usePluginRunStore } from "./plugin_run";
import { usePluginRunResultStore } from "./plugin_run_result";
import { useClusterTimelineItemStore } from "./cluster_timeline_item";

import { useShotStore } from "./shot";

// useStore could be anything like useUser, useCart
// the first argument is a unique id of the store across your application
export const useExporterStore = defineStore("exporter", {
  // other options...
  state: () => {
    return {
      exporterRuns: {},
      exporterRunPollers: {},
    };
  },
  getters: {},
  actions: {
    stopPolling(jobId) {
      if (this.exporterRunPollers[jobId]) {
        clearInterval(this.exporterRunPollers[jobId]);
        delete this.exporterRunPollers[jobId];
      }
    },
    pollExporterStatus(jobId, intervalMs = 2000) {
      // Prevent duplicate pollers for the same jobId
      if (this.exporterRunPollers[jobId]) {
        clearInterval(this.exporterRunPollers[jobId]);
      }

      const poll = async () => {
        try {
          // Adjust this URL to match your Django status endpoint
          const res = await axios.get(
            `${config.API_LOCATION}/video/export/status/${jobId}`
          );

          if (res.data.status === "ok") {
            const run = res.data.export_run; // The dict from ExporterRun.to_dict()
            this.exportRuns[jobId] = run;

            if (run.status === "DONE") {
              this.stopPolling(jobId);
              await this.downloadExportResult(jobId);
              this.isLoading = false;
            } else if (run.status === "ERROR" || run.status === "CANCELED") {
              this.stopPolling(jobId);
              this.isLoading = false;
              console.error("Export failed:", run.error_message);
            }
          }
        } catch (error) {
          console.error("Error polling export status:", error);
          this.stopPolling(jobId);
          this.isLoading = false;
        }
      };

      // Run immediately once, then every `intervalMs`
      poll();
      this.exporterRunPollers[jobId] = setInterval(poll, intervalMs);
    },
    async export({ format, parameters = [], videoId = null }) {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      const formData = new FormData();
      formData.append("format", format);
      let jsonParameters = [];
      // formData.append("parameters", JSON.stringify(parameters));
      parameters.forEach((p) => {
        if ("file" in p) {
          formData.append(`file_${p.name}`, p.file);
        } else {
          jsonParameters.push(p);
        }
      });
      formData.append("parameters", JSON.stringify(jsonParameters));

      //use video id or take it from the current video
      let video_id = videoId;
      if (videoId) {
        video_id = videoId;
      } else {
        const playerStore = usePlayerStore();
        const video = playerStore.videoId;
        if (video) {
          video_id = video;
        }
      }
      formData.append("video_id", video_id);
      console.log(formData);
      return axios
        .post(`${config.API_LOCATION}/video/export`, formData, {
          headers: { "Content-Type": "multipart/form-data" },
        })
        .then((res) => {
          console.log("data");
          console.log(res.data);
          if (res.data.status === "ok") {
            this.pollExporterStatus(res.data.job_id);
          }
        })
        .finally(() => {
          this.isLoading = false;
        });
    },
    async downloadExporterResult(jobId) {
      try {
        const res = await axios.get(
          `${config.API_LOCATION}/video/export/download/${run.id}`,
          {
            responseType: "blob", // Tells Axios to write binary data directly to a Blob
          }
        );

        // Create a temporary object URL pointing to the downloaded Blob
        const blob = new Blob([res.data], {
          type: res.headers["content-type"] || "application/octet-stream",
        });
        const url = window.URL.createObjectURL(blob);

        const link = document.createElement("a");
        link.href = url;
        link.download = `${run.name}.${run.ext}`;
        document.body.appendChild(link);
        link.click();

        // Clean up DOM and free browser memory
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
      } catch (error) {
        console.error("Failed to download exported file:", error);
      }
    },
  },
});
