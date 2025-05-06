<template>
  <v-main class="main" @keydown.native="onKeyDown" tabindex="0" ref="main">
    <v-container fluid>
      <v-row class="ma-2">
        <v-col cols="6">
          <v-card class="d-flex flex-column flex-nowrap px-2" elevation="2" v-resize="onVideoResize" ref="videoCard">
            <v-row>
              <v-card-title>
                {{ playerStore.videoName }}
              </v-card-title>
            </v-row>

            <v-row class="flex-grow-1">
              <v-col>
                <VideoPlayer @resize="onVideoResize" />
              </v-col>
            </v-row>
            <v-row class="mb-2 px-4">
              <TimeSelector width="100%" @resize="onVideoResize" />
            </v-row>
          </v-card>
        </v-col>

        <v-col cols="6">
          <div v-if="isLoading" class="loading-container">
            <div class="spinner">
              <i class="mdi mdi-loading mdi-spin"></i>
            </div>
            <div class="loading-text">Loading...</div>
          </div>
          <v-card v-else elevation="2" ref="resultCard" :height="resultCardHeight">
            <div class="sticky-tabs-bar">
              <v-tabs v-model="tab" centered show-arrows>
                <v-tabs-slider />
                <v-tab>Shots</v-tab>
                <v-tab>Faces</v-tab>
                <v-tab>Places</v-tab>
                <v-tab>Annotations</v-tab>
                <v-tab>Transcript</v-tab>
                <v-tab>Word Cloud</v-tab>
              </v-tabs>
            </div>

            <v-tabs-items v-model="tab" style="height: 92%;">
              <v-tab-item style="height: 100%">

                <div :class="['d-flex', 'flex-column', 'px-2', 'mx-4', 'my-2']">
                  <v-select solo hide-details dense :items="shotsList" v-model="selectedShots" />
                </div>
                <ShotsOverview />
              </v-tab-item>

              <v-tab-item style="height: 100%">

                <div :class="['d-flex', 'flex-column', 'px-2', 'mx-4', 'my-2']">
                  <v-select solo hide-details dense :items="faceClusteringList" v-model="selectedFaceClustering" />
                </div>
                <div :class="['d-flex', 'flex-column', 'px-2', 'mx-4', 'my-2']">
                  <PersonGraph />
                </div>
                <ClusterTimelineItemOverview name="Face" :clusters="faceClusters"></ClusterTimelineItemOverview>
              </v-tab-item>

              <v-tab-item style="height: 100%">

                <div :class="['d-flex', 'flex-column', 'px-2', 'mx-4', 'my-2']">
                  <v-select solo hide-details dense :items="placeClusteringList" v-model="selectedPlaceClustering" />
                </div>
                <ClusterTimelineItemOverview name="Place" :clusters="placeClusters"></ClusterTimelineItemOverview>
              </v-tab-item>

              <v-tab-item>
                <CurrentEntitiesOverView />
              </v-tab-item>

              <v-tab-item style="height: 100%">
                <TranscriptOverview />
              </v-tab-item>

              <v-tab-item>
                <WordcloudCard />
              </v-tab-item>
            </v-tabs-items>
          </v-card>
        </v-col>
      </v-row>

      <v-row class="ma-2">
        <v-col>
          <VisualizationMenu></VisualizationMenu>
        </v-col>
      </v-row>

      <v-row class="ma-2">
        <v-col>
          <v-card class="d-flex flex-column flex-nowrap" max-width="100%" elevation="2" scrollable="False">
            <v-card-title> Timelines </v-card-title>
            <v-flex grow class="mb-2 px-4">
              <Timeline ref="timeline" width="100%"> </Timeline>
            </v-flex>
          </v-card>
        </v-col>
      </v-row>
      <ModalTimelineSegmentAnnotate :show.sync="annotationDialog.show" />
    </v-container>
  </v-main>
</template>

<script>
import VideoPlayer from "@/components/VideoPlayer.vue";
import TranscriptOverview from "@/components/TranscriptOverview.vue";
import Timeline from "@/components/Timeline.vue";
import TimeSelector from "@/components/TimeSelector.vue";
import CurrentEntitiesOverView from "@/components/CurrentEntitiesOverView.vue";
import ModalTimelineSegmentAnnotate from "@/components/ModalTimelineSegmentAnnotate.vue";
import ShotsOverview from "@/components/ShotsOverview.vue";
import WordcloudCard from "@/components/WordcloudCard.vue";
import VisualizationMenu from "@/components/VisualizationMenu.vue";
import PersonGraph from "../components/PersonGraph.vue";

import * as Keyboard from "../plugins/keyboard.js";
// import store from "../store/index.js";

import { mapStores } from "pinia";
import { useVideoStore } from "@/store/video";
import { usePlayerStore } from "@/store/player";
import { useTimelineStore } from "@/store/timeline";
import { useTimelineSegmentStore } from "@/store/timeline_segment";
import { useTimelineSegmentAnnotationStore } from "@/store/timeline_segment_annotation";
import { useShortcutStore } from "@/store/shortcut";
import { useAnnotationShortcutStore } from "../store/annotation_shortcut.js";
import { usePluginRunStore } from "../store/plugin_run.js";
import { useClusterTimelineItemStore } from "../store/cluster_timeline_item";
import { useShotStore } from "@/store/shot";
import ClusterTimelineItemOverview from "../components/ClusterTimelineItemOverview.vue";

export default {
  data() {
    return {
      //timer
      fetchPluginTimer: null,

      selectedShotsProxy: null,
      selectedFaceClusteringProxy: null,
      selectedPlaceClusteringProxy: null,

      selectedTimelineProxy: null,
      tab: null,
      addedAnnotation: null,
      labels: [],
      selectedLabel: null,
      annotationsLUT: {},
      //
      annotationDialog: {
        show: false,
      },
      isLoading: true,
      resultCardHeight: 0,
    };
  },
  methods: {
    onVideoResize() {
      this.resultCardHeight = this.$refs.videoCard.$el.clientHeight;
    },
    onKeyDown(event) {
      const lastSelectedTimeline = this.timelineStore.lastSelected;
      const lastSelectedTimelineSegment =
        this.timelineSegmentStore.lastSelected;
      if (!lastSelectedTimeline) {
        if (
          event.key == "ArrowDown" ||
          event.key == "ArrowUp" ||
          event.key == "ArrowLeft" ||
          event.key == "ArrowRight"
        ) {
          const selectedTimeline = this.timelineStore.getNext(null);
          this.timelineStore.addToSelection(selectedTimeline.id);
          const timelineSegments = this.timelineSegmentStore.forTimeline(
            selectedTimeline.id
          );
          if (timelineSegments.length > 0) {
            const selectedTimelineSegment = timelineSegments[0];
            this.timelineSegmentStore.addToSelection(
              selectedTimelineSegment.id
            );
          }
          return;
        }
      }

      if (event.key == "ArrowDown") {
        const nextTimeline = this.timelineStore.getNext(
          lastSelectedTimeline.id
        );
        if (!nextTimeline) {
          return;
        }
        // delete old selection
        if (!event.ctrlKey) {
          this.timelineStore.clearSelection();
          this.timelineSegmentStore.clearSelection();
        }

        this.timelineStore.addToSelection(nextTimeline.id);
        const timelineSegments = this.timelineSegmentStore.forTimeline(
          nextTimeline.id
        );
        if (timelineSegments.length > 0) {
          const nextSelectedTimelineSegment = timelineSegments[0];
          this.timelineSegmentStore.addToSelection(
            nextSelectedTimelineSegment.id
          );
        }
        event.preventDefault();
      } else if (event.key == "ArrowUp") {
        const nextTimeline = this.timelineStore.getPrevious(
          lastSelectedTimeline.id
        );
        if (!nextTimeline) {
          return;
        }
        // delete old selection
        if (!event.ctrlKey) {
          this.timelineStore.clearSelection();
          this.timelineSegmentStore.clearSelection();
        }

        this.timelineStore.addToSelection(nextTimeline.id);
        const timelineSegments = this.timelineSegmentStore.forTimeline(
          nextTimeline.id
        );
        if (timelineSegments.length > 0) {
          const nextSelectedTimelineSegment = timelineSegments[0];
          this.timelineSegmentStore.addToSelection(
            nextSelectedTimelineSegment.id
          );
        }
        event.preventDefault();
      } else if (event.key == "ArrowLeft") {
        if (!lastSelectedTimelineSegment) {
          return;
        }
        const nextTimelineSegment =
          this.timelineSegmentStore.getPreviousOnTimeline(
            lastSelectedTimelineSegment.id
          );
        if (!nextTimelineSegment) {
          return;
        }
        // jump the player to the start time of this segment
        this.playerStore.setTargetTime(nextTimelineSegment.start);
        if (!event.ctrlKey) {
          this.timelineSegmentStore.clearSelection();
        }
        this.timelineSegmentStore.addToSelection(nextTimelineSegment.id);
        event.preventDefault();
      } else if (event.key == "ArrowRight") {
        if (!lastSelectedTimelineSegment) {
          return;
        }
        const nextTimelineSegment = this.timelineSegmentStore.getNextOnTimeline(
          lastSelectedTimelineSegment.id
        );
        if (!nextTimelineSegment) {
          return;
        }
        // jump the player to the start time of this segment
        this.playerStore.setTargetTime(nextTimelineSegment.start);
        if (!event.ctrlKey) {
          this.timelineSegmentStore.clearSelection();
        }
        this.timelineSegmentStore.addToSelection(nextTimelineSegment.id);
        event.preventDefault();
      } else if (event.key == "Enter") {
        this.onAnnotateSegment();
        event.preventDefault();
      }

      // handling shortcut
      const keys = [];
      if (event.ctrlKey) {
        keys.push("ctrl");
      }
      if (event.shiftKey) {
        keys.push("shift");
      }
      if (event.key.length === 1) {
        keys.push(event.key.toLowerCase());
      }

      const keysString = Keyboard.generateKeysString(keys);
      const shortcuts = this.shortcutStore.getByKeys(keysString);

      if (shortcuts.length > 0) {
        shortcuts.forEach((shortcut) => {
          const annotationShortcut = this.annotationShortcutStore.forShortcut(
            shortcut.id
          );

          if (annotationShortcut) {
            if (lastSelectedTimelineSegment) {
              this.timelineSegmentStore.toggle({
                timelineSegmentId: lastSelectedTimelineSegment.id,
                annotationId: annotationShortcut.annotation_id,
              });
            }
          }
        });
      }
    },
    onAnnotateSegment() {
      if (this.timelineSegmentStore.lastSelected) {
        this.$nextTick(() => {
          this.annotationDialog.show = true;
        });
      }
    },
    async fetchData({ addResults = true }) {
      // Ask backend about all videos+

      await this.videoStore.fetch({
        videoId: this.$route.params.id,
        addResults: addResults,
      });
    },
    async fetchPlugin() {
      await this.pluginRunStore.fetchForVideo({
        videoId: this.$route.params.id,
        fetchResults: true,
      });
    },
  },
  computed: {
    pluginInProgress() {
      return this.pluginRunStore.pluginInProgress;
    },
    timelines() {
      return this.timelineStore.forVideo(this.$route.params.id);
    },
    timelineNames() {
      return this.timelines.map((e) => e.name);
    },
    faceClusters() {
      return this.clusterTimelineItemStore.latestFaceClustering();
    },
    placeClusters() {
      return this.clusterTimelineItemStore.latestPlaceClustering();
    },
    selectedShots: {
      get() {
        const selectedShots = this.shotStore.selectedShots;
        return this.selectedShotsProxy === null ? selectedShots : this.selectedShotsProxy;
      },
      set(val) {
        this.selectedShotsProxy = val;

        this.shotStore.setSelectedShots({ shotTimeline: val });
      },
    },
    shotsList() {
      return this.shotStore.shotsList.map((e) => { return { text: e.name, value: e.index } });
    },
    selectedFaceClustering: {
      get() {
        const selectedFaceClustering = this.clusterTimelineItemStore.selectedFaceClustering;
        return this.selectedFaceClusteringProxy === null ? selectedFaceClustering : this.selectedFaceClusteringProxy;
      },
      set(val) {
        this.selectedFaceClusteringProxy = val;

        this.clusterTimelineItemStore.setSelectedFaceClustering({ pluginRunId: val });
      },
    },
    faceClusteringList() {
      return this.clusterTimelineItemStore.faceClusteringList.map((e) => { return { text: e.name, value: e.index } });
    },
    selectedPlaceClustering: {
      get() {
        const selectedPlaceClustering = this.clusterTimelineItemStore.selectedPlaceClustering;
        return this.selectedPlaceClusteringProxy === null ? selectedPlaceClustering : this.selectedPlaceClusteringProxy;
      },
      set(val) {
        this.selectedPlaceClusteringProxy = val;

        this.clusterTimelineItemStore.setSelectedPlaceClustering({ pluginRunId: val });
      },
    },
    placeClusteringList() {
      return this.clusterTimelineItemStore.placeClusteringList.map((e) => { return { text: e.name, value: e.index } });
    },
    selectedTimeline: {
      get() {
        return this.selectedTimelineProxy === null
          ? this.timelines[0]
          : this.selectedTimelineProxy;
      },
      set(val) {
        this.selectedTimelineProxy = val;
      },
    },

    ...mapStores(
      useVideoStore,
      usePluginRunStore,
      usePlayerStore,
      useTimelineStore,
      useShotStore,
      useTimelineSegmentStore,
      useTimelineSegmentAnnotationStore,
      useShortcutStore,
      useAnnotationShortcutStore,
      useClusterTimelineItemStore,
    ),
  },
  async created() {
    // fetch the data when the view is created and the data is
    await this.fetchData({ addResults: true });
    this.isLoading = false;
  },
  components: {
    VideoPlayer,
    TranscriptOverview,
    Timeline,
    TimeSelector,
    CurrentEntitiesOverView,
    ModalTimelineSegmentAnnotate,
    ShotsOverview,
    WordcloudCard,
    VisualizationMenu,
    PersonGraph,
    ClusterTimelineItemOverview
  },

  watch: {
    pluginInProgress(newState) {
      if (newState) {
        this.fetchPluginTimer = setInterval(
          function () {
            this.fetchPlugin({ addResults: false });
          }.bind(this),
          1000
        );
      }
      if (!newState) {
        clearInterval(this.fetchPluginTimer);
      }
    },
    isLoading(value) {
      if (!value) {
        this.resultCardHeight = this.$refs.videoCard.$el.clientHeight;
        this.$refs.main.$el.focus();
      }
    }
  },
};
</script>

<style scoped>
.logo>img {
  max-height: 56px;
}

.sticky-tabs-bar {
  position: sticky;
  top: 0;
  z-index: 1;
  background-color: white;
  /* Adjust the background color if needed */
}

.card-title {
  font-size: 64;
}

.timeline-bar {
  height: 80px;
}

.main:focus {
  outline: none;
}

.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 50vh;
}

.spinner {
  font-size: 48px;
  color: #ac1414;
}

.loading-text {
  margin-top: 10px;
  font-size: 18px;
}
</style>
