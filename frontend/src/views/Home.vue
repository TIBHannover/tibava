<template>
  <v-app>
    <v-main>
      <v-container v-if="userStore.loggedIn" class="py-8 px-6" fluid>
        <v-container
          class="d-flex flex-wrap video-gallery align-content-center"
        >
          <v-card
            elevation="2"
            width="420px"
            :loading="item.loading"
            v-for="item in videos"
            :key="item.id"
          >
            <v-card-title class="video-overview-title">{{
              item.name
            }}</v-card-title>
            <v-card-text>
              <div>Video ID: {{ item.id }}</div>
              <div>
                Length:
                {{ get_display_time(item.duration) }}
              </div>
              <div>Uploaded: {{ item.date.slice(0, 10) }}</div>
              <div>Timelines: {{ item.num_timelines }}</div>

              <v-card-actions class="actions">
                <v-btn outlined @click="showVideo(item.id)">
                  <v-icon>{{ "mdi-movie-search-outline" }}</v-icon> Analyse
                </v-btn>
                <ModalVideoRename :video="item.id">
                  <template v-slot:activator="on">
                    <v-btn outlined v-on="on">
                      <v-icon left>{{ "mdi-pencil" }}</v-icon>
                      {{ $t("modal.video.rename.link") }}
                    </v-btn>
                  </template>
                </ModalVideoRename>
                <!-- <ModalVideoRename :video="item.id" /> -->
                <v-btn color="red" outlined @click="deleteVideo(item.id)">
                  <v-icon>{{ "mdi-trash-can-outline" }}</v-icon> Delete
                </v-btn>
                <v-checkbox
                  :value="videoSelected[item.id]"
                  color="primary"
                  class="ms-2"
                  @change="(value) => selectVideo(item.id, value)"
                ></v-checkbox>
              </v-card-actions>
            </v-card-text>
            <v-progress-linear
              :value="videosProgress[item.id]"
            ></v-progress-linear>
          </v-card>
        </v-container>
      </v-container>
      <v-container v-else>
        <v-col justify="space-around">
          <v-card class="welcome pa-5">
            <v-card-title>
              <h1 class="text-h2">{{ $t("welcome.title") }}</h1>
            </v-card-title>

            <v-card-text>
              <p v-html="$t('welcome.text')"></p>
              <h2 class="text-h5 mb-2">{{ $t("welcome.demo_title") }}</h2>
              <p>
                <video id="welcome-video" controls>
                  <source
                    src="https://tib.eu/cloud/s/sMmqWqWYict3Zpb/download/TIB-AV-A_Einfuehrung_2.mp4"
                    type="video/mp4"
                  />
                </video>
              </p>
              <h2 class="text-h5 mb-1 mt-4">{{ $t("welcome.login_title") }}</h2>
              <p v-html="$t('welcome.login_text')"></p>
              <h2 class="text-h5 mb-1 mt-4">
                {{ $t("welcome.format_title") }}
              </h2>
              <p v-html="$t('welcome.format_text')"></p>
            </v-card-text>
          </v-card>
        </v-col>
      </v-container>
    </v-main>
  </v-app>
</template>

<script>
import router from "../router";
import ModalPlugin from "@/components/ModalPlugin.vue";
import ModalVideoUpload from "@/components/ModalVideoUpload.vue";
import ModalVideoRename from "@/components/ModalVideoRename.vue";
import TimeMixin from "../mixins/time";
import { mapStores } from "pinia";
import { useVideoStore } from "@/store/video.js";
import { useUserStore } from "@/store/user.js";
import { usePluginRunStore } from "@/store/plugin_run.js";
import { useTimelineStore } from "@/store/timeline";
import { usePluginRunResultStore } from "../store/plugin_run_result";

export default {
  mixins: [TimeMixin],
  data() {
    return {
      showModalPlugin: false,
      fetchPluginTimer: null,
    };
  },
  mounted() {
    this.fetchData();
  },
  beforeDestroy() {
    if (this.fetchPluginTimer) {
      clearInterval(this.fetchPluginTimer);
    }
  },
  methods: {
    selectVideo(video_id, value) {
      this.videoStore.toggleSelected(video_id);
    },
    deleteVideo(video_id) {
      this.videoStore.delete(video_id);
    },
    showVideo(video_id) {
      router.push({ path: `/videoanalysis/${video_id}` });
    },
    async fetchData(fetchTimelines = false) {
      await this.videoStore.fetchAll();
      await this.pluginRunStore.fetchAll({ addResults: false });
      if (fetchTimelines) {
        await this.timelineStore.fetchAll({ addResultsType: true });
      }
    },
  },
  computed: {
    videoSelected() {
      let test = this.videoStore.all.reduce(
        (prev, e) => ({
          ...prev,
          [e.id]: this.videoStore.videoSelected.includes(e.id),
        }),
        {}
      );

      return test;
    },
    videos() {
      return this.videoStore.all;
    },
    videosProgress() {
      const progress = {};
      for (const vid of this.videos) {
        const runs = this.pluginRunStore.forVideo(vid.id);
        progress[vid.id] =
          (runs.filter((r) => r.status !== "RUNNING" && r.status !== "QUEUED")
            .length *
            100) /
          runs.length;
      }
      return progress;
    },
    ...mapStores(
      useVideoStore,
      usePluginRunStore,
      useUserStore,
      useTimelineStore,
      usePluginRunResultStore
    ),
  },
  watch: {
    "userStore.loggedIn": function (value, oldValue) {
      if (!oldValue && value) {
        // fetch user's videos after login
        this.fetchData();
      }
    },
    "pluginRunStore.pluginInProgress": {
      immediate: true,
      handler(newState) {
        if (newState) {
          this.fetchPluginTimer = setInterval(
            function () {
              this.fetchData();
            }.bind(this),
            2000
          );
        } else {
          clearInterval(this.fetchPluginTimer);
        }
      },
    },
    videosProgress(newState, oldState) {
      if (
        Object.keys(newState).some(
          (k) => oldState && (!(k in oldState) || newState[k] !== oldState[k])
        )
      ) {
        // already fetch partial progress and not just when all plugins are finished
        this.fetchData(true);
      }
    },
  },
  components: {
    ModalVideoUpload,
    ModalVideoRename,
    ModalPlugin,
  },
};
</script>

<style>
.video-overview-title {
  display: block !important;
  white-space: nowrap;
  overflow: hidden;
  width: 100%;
  text-overflow: ellipsis;
}

.video-gallery > * {
  margin: 8px;
}

.video-gallery > * {
  margin: 8px;
}

.actions > .v-btn:not(:first-child) {
  margin-left: 8px !important;
}
#welcome-video {
  margin-left: auto;
  margin-right: auto;
  display: block;
  border-style: outset;
  border-color: black;
  max-width: 800px;
}
</style>
