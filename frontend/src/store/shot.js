import axios from "../plugins/axios";
import config from "../../app.config";
import { defineStore } from "pinia";

import { usePlayerStore } from "./player";
import { usePluginRunStore } from "./plugin_run";
import { useTimelineStore } from "./timeline";
import { useTimelineSegmentStore } from "./timeline_segment";
import { usePluginRunResultStore } from "./plugin_run_result";

export const useShotStore = defineStore("shot", {
  state: () => {
    return {
      isLoading: false,
      selectedShots: null,
    };
  },
  getters: {
    shotsList() {

      const timelineStore = useTimelineStore();
      const playerStore = usePlayerStore();

      let timeline = timelineStore
        .forVideo(playerStore.videoId)
        .filter((e) => {
          return e.type == "ANNOTATION";
        })

      if (timeline.length) {
        return timeline.map((e, i) => {
          return {
            index: e.id,
            name: e.name
          }
        })
      }

      return []

    },
    shots(state) {

      const pluginRunStore = usePluginRunStore();
      const pluginRunResultStore = usePluginRunResultStore();
      const timelineStore = useTimelineStore();
      const timelineSegmentStore = useTimelineSegmentStore();
      const playerStore = usePlayerStore();

      let results = []

      let selectedShots = state.selectedShots
      if (!state.selectedShots) {

        let timeline = timelineStore
          .forVideo(playerStore.videoId)
          .filter((e) => {
            return e.type == "ANNOTATION";
          })

        if (!timeline.length) {
          console.error("Shots: No annotation timeline")
          return results
        }
        selectedShots = timeline[0].id
      }

      results = timelineSegmentStore.forTimeline(selectedShots).map((e) => {
        return {
          start: e.start,
          end: e.end,
        };
      })

      // selection of thumbnails to be used
      let thumbnail = pluginRunStore
        .forVideo(playerStore.videoId)
        .filter((e) => {
          return e.type == "thumbnail" && e.status == "DONE";
        })
        .map((e) => {
          e.results = pluginRunResultStore.forPluginRun(e.id);
          return e;
        })
        .sort((a, b) => {
          return new Date(b.date) - new Date(a.date);
        });

      if (!thumbnail.length) {
        console.error("Shots: No thumbnail run")
        return [];
      }
      thumbnail = thumbnail.at(0); // use latest thumbnails

      // create thumbnail dict indicating the thumbnail for a specific time
      let thumbnail_list = [];
      let delta_time = 0.2;
      if (
        "results" in thumbnail &&
        thumbnail.results.length > 0 &&
        "data" in thumbnail.results[0]
      ) {
        delta_time = thumbnail.results[0].data.images[0].delta_time;
        thumbnail_list = thumbnail.results[0].data.images.map((e) => {
          return (
            config.THUMBNAIL_LOCATION +
            `/${e.id.substr(0, 2)}/${e.id.substr(2, 2)}/${e.id}.${e.ext}`
          );
        });
      }

      // assign thumbnails to shots
      results = results.map((e, i) => {
        return {
          id: i + 1,
          start: e.start,
          end: e.end,
          thumbnails: [
            thumbnail_list[
            Math.min(
              Math.ceil(e.start / delta_time),
              thumbnail_list.length - 1
            )
            ],
            thumbnail_list[
            Math.round((e.start + (e.end - e.start) / 2) / delta_time)
            ],
            thumbnail_list[Math.floor(e.end / delta_time)],
          ],
        };
      });

      return results;
    }
  },
  actions: {
    async setSelectedShots({ videoId = null, shotTimeline = null }) {
      this.selectedShots = shotTimeline;

      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      //use video id or take it from the current video
      let params = { timeline_id: shotTimeline };
      if (videoId) {
        params.video_id = videoId;
      } else {
        const playerStore = usePlayerStore();
        const videoId = playerStore.videoId;
        if (videoId) {
          params.video_id = videoId;
        }
      }

      return axios
        .post(`${config.API_LOCATION}/video/analysis/setselectedshots`, params)
        .then((res) => {
          if (res.data.status === "ok") {


          }
        })
        .catch(() => { })
        .finally(() => {
          this.isLoading = false;
        });
    },
    async fetchForVideo({ videoId = null }) {
      if (this.isLoading) {
        return;
      }
      this.isLoading = true;

      //use video id or take it from the current video
      let params = {};
      if (videoId) {
        params.video_id = videoId;
      } else {
        const playerStore = usePlayerStore();
        const videoId = playerStore.videoId;
        if (videoId) {
          params.video_id = videoId;
        }
      }
      return axios
        .get(`${config.API_LOCATION}/video/analysis/get`, { params })
        .then((res) => {
          if (res.data.status === "ok") {
            let selectedShots = res.data.entry.selected_shots;
            if (!selectedShots) {
              let timeline = timelineStore
                .forVideo(playerStore.videoId)
                .filter((e) => {
                  return e.type == "ANNOTATION";
                })

              if (!timeline.length) {
                console.error("Shots: No annotation timeline")
                return results
              }
              selectedShots = timeline[0].id;
            }

            this.selectedShots = selectedShots;

            console.log("selectedShots " + this.selectedShots);

          }
        })
        .catch(() => { })
        .finally(() => {
          this.isLoading = false;
        });
      // .catch((error) => {
      //     const info = { date: Date(), error, origin: 'collection' };
      //     commit('error/update', info, { root: true });
      // });
    },
  }

},
);
