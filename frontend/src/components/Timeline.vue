<template>
  <div style="width: 100%; min-height: 100px">
    <v-row>
      <v-col cols="3" style="margin: 0px; padding: 0px; padding-right: 10px">
        <div style="height: 40px; margin-top: 4px; margin-bottom: 4px">
          <v-menu bottom right>
            <template v-slot:activator="{ on, attrs }">
              <v-btn
                v-bind="attrs"
                v-on="on"
                style="height: 40px; width: 100%; height: 100%"
              >
                <v-icon left>mdi-cog</v-icon>
                {{ $t("modal.timeline.menu.title") }}
              </v-btn>
            </template>
            <v-list>
              <v-list-item link>
                <ModalCreateTimeline @close="menu.show = false" />
              </v-list-item>
              <v-list-item link>
                <ModalImportTimeline @close="menu.show = false" />
              </v-list-item>
            </v-list>
          </v-menu>
        </div>

        <DraggableTree
          draggable="draggable"
          cross-tree="cross-tree"
          class="timelinetree"
          :data="timelineHierarchy"
          :indent="25"
          :space="0"
          @change="change"
          @nodeOpenChanged="nodeOpenChanged"
        >
          <div slot-scope="{ data, store }">
            <template v-if="!data.isDragPlaceHolder">
              <v-app-bar
                dense
                color="white"
                style="
                  height: 50px;
                  margin-top: 4px;
                  margin-bottom: 4px;
                  width: 100%;
                "
              >
                <v-icon
                  v-if="data.children && data.children.length"
                  @click="store.toggleOpen(data)"
                  >{{ data.open ? "mdi-minus" : "mdi-plus" }}</v-icon
                >
                <!-- <v-tooltip top>
                  <template v-slot:activator="{ on, attrs }">
                    <v-app-bar-title v-bind="attrs" v-on="on">
                      {{ data.text }}
                    </v-app-bar-title>
                  </template>
                  <span>{{ data.text }}</span>
                </v-tooltip> -->
                <v-app-bar-title>
                  {{ data.text }}
                </v-app-bar-title>

                <v-spacer></v-spacer>

                <v-menu bottom right>
                  <template v-slot:activator="{ on, attrs }">
                    <v-btn icon small>
                      <v-icon v-bind="attrs" v-on="on"
                        >mdi-dots-vertical</v-icon
                      >
                    </v-btn>
                  </template>
                  <v-list>
                    <v-list-item>
                      <ModalCopyTimeline :timeline="data.id" />
                    </v-list-item>
                    <v-list-item>
                      <ModalRenameTimeline :timeline="data.id" />
                    </v-list-item>
                    <v-list-item v-if="data.type == 'PLUGIN_RESULT'">
                      <ModalVisualizationTimeline :timeline="data.id" />
                    </v-list-item>
                    <v-list-item v-if="data.type == 'PLUGIN_RESULT'">
                      <ModalExportResult :timeline="data.id" />
                    </v-list-item>
                    <v-list-item>
                      <ModalDeleteTimeline :timeline="data.id" />
                    </v-list-item>
                  </v-list>
                </v-menu>
              </v-app-bar>
            </template>
          </div>
        </DraggableTree>
      </v-col>

      <v-col ref="container" cols="9" style="margin: 0; padding: 0">
        <canvas style="width: 100%" ref="canvas" resize> </canvas>
      </v-col>
    </v-row>

    <v-tooltip
      top
      v-model="timelineTooltip.show"
      :position-x="timelineTooltip.x"
      :position-y="timelineTooltip.y"
      absolute
    >
      <span>{{ timelineTooltip.label }}</span>
    </v-tooltip>

    <v-menu
      v-model="segmentMenu.show"
      :position-x="segmentMenu.x"
      :position-y="segmentMenu.y - 10"
      absolute
      offset-y
    >
      <v-list>
        <v-list-item link v-on:click="onAnnotateSelection">
          <v-list-item-title>
            <v-icon left>{{ "mdi-pencil" }}</v-icon>
            {{ $t("timelineSegment.annotate.selection") }}
          </v-list-item-title>
        </v-list-item>
        <v-list-item link v-on:click="onAnnotateSelectionRange">
          <v-list-item-title>
            <v-icon left>{{ "mdi-pencil" }}</v-icon>
            {{ $t("timelineSegment.annotate.range") }}
          </v-list-item-title>
        </v-list-item>

        <!-- <v-list-item link v-on:click="onDeleteSegment">
          <v-list-item-title>
            <v-icon left>{{ "mdi-delete" }}</v-icon>
            {{ $t("timelineSegment.delete") }}
          </v-list-item-title>
        </v-list-item> -->

        <v-list-item link v-on:click="onSplitSegment">
          <v-list-item-title>
            <v-icon left>{{ "mdi-content-cut" }}</v-icon>
            {{ $t("timelineSegment.split") }}
          </v-list-item-title>
        </v-list-item>
        <!-- <v-list-item link v-on:click="onMergeSelection">
          <v-list-item-title>
            <v-icon left>{{ "mdi-pencil" }}</v-icon>
            {{ $t("timelineSegment.merge.selection") }}
          </v-list-item-title>
        </v-list-item>
        <v-list-item link v-on:click="onMergeSelectionRange">
          <v-list-item-title>
            <v-icon left>{{ "mdi-pencil" }}</v-icon>
            {{ $t("timelineSegment.merge.range") }}
          </v-list-item-title>
        </v-list-item> -->

        <v-list-item link v-on:click="onMergeSegmentsLeft">
          <v-list-item-title>
            <v-icon left>{{ "mdi-arrow-expand-left" }}</v-icon>
            {{ $t("timelineSegment.mergeleft") }}
          </v-list-item-title>
        </v-list-item>

        <v-list-item link v-on:click="onMergeSegmentsRight">
          <v-list-item-title>
            <v-icon left>{{ "mdi-arrow-expand-right" }}</v-icon>
            {{ $t("timelineSegment.mergeright") }}
          </v-list-item-title>
        </v-list-item>

        <v-list-item
          v-if="selectedTimelineSegments.length > 1"
          link
          v-on:click="onMergeSegments"
        >
          <v-list-item-title>
            <v-icon left>{{ "mdi-merge" }}</v-icon>
            {{ $t("timelineSegment.merge") }}
          </v-list-item-title>
        </v-list-item>
      </v-list>
    </v-menu>
    <ModalTimelineSegmentAnnotate
      :show.sync="annotationDialog.show"
      :annotate-range="annotationDialog.annotateRange"
      :timeline-id="annotationDialog.timelineId"
    />
  </div>
</template>

<script>
import TimeMixin from "../mixins/time";
import { DraggableTree } from "vue-draggable-nested-tree";
import ModalRenameTimeline from "@/components/ModalRenameTimeline.vue";
import ModalCopyTimeline from "@/components/ModalCopyTimeline.vue";
import ModalDeleteTimeline from "@/components/ModalDeleteTimeline.vue";
import ModalExportResult from "@/components/ModalExportResult.vue";
import ModalCreateTimeline from "@/components/ModalCreateTimeline.vue";
import ModalVisualizationTimeline from "@/components/ModalVisualizationTimeline.vue";
import ModalImportTimeline from "@/components/ModalImportTimeline.vue";
import ModalTimelineSegmentAnnotate from "@/components/ModalTimelineSegmentAnnotate.vue";

import {
  AnnotationTimeline,
  ColorTimeline,
  ScalarLineTimeline,
  ScalarColorTimeline,
  TimeScale,
  TimeBar,
  HistTimeline,
  generateFont,
} from "../plugins/draw";

import * as PIXI from "pixi.js";

import { mapStores } from "pinia";
import { useTimelineStore } from "@/store/timeline";
import { useTimelineSegmentStore } from "@/store/timeline_segment";
import { useTimelineSegmentAnnotationStore } from "@/store/timeline_segment_annotation";
import { useAnnotationStore } from "@/store/annotation";
import { useAnnotationCategoryStore } from "@/store/annotation_category";
import { usePlayerStore } from "@/store/player";
import { useVideoStore } from "@/store/video";
import { usePluginRunResultStore } from "@/store/plugin_run_result";

export default {
  mixins: [TimeMixin],
  props: {
    headerWidth: {
      type: Number,
      default: 0,
    },
    scaleHeight: {
      type: Number,
      default: 40,
    },
    timelineHeight: {
      type: Number,
      default: 50,
    },
    gap: {
      type: Number,
      default: 4,
    },
    headerStyle: {
      type: Object,
      default: () => {
        return {
          shadowColor: "rgba(0, 0, 0, 0.25)",
          shadowBlur: 6,
          shadowOffset: { x: 0, y: 3 },
          fillColor: "white",
        };
      },
    },
    timeStyle: {
      type: Object,
      default: () => {
        return {
          shadowColor: "rgba(0, 0, 0, 0.25)",
          shadowBlur: 6,
          shadowOffset: { x: 0, y: 3 },
          fillColor: "white",
        };
      },
    },
    timelineStyle: {
      type: Object,
      default: () => {
        return {
          shadowColor: "rgba(0, 0, 0, 0.25)",
          shadowBlur: 6,
          shadowOffset: { x: 0, y: 3 },
          fillColor: "white",
        };
      },
    },
    segmentStyle: {
      type: Object,
      default: () => {
        return {
          fillColor: "red",
        };
      },
    },
    width: {},
  },
  data() {
    return {
      //disable event loop if not loaded
      enabled: false,

      app: null,
      timelineObjects: [],
      timeScaleObjects: [],
      timeBarsObjects: [],

      timelineHierarchy: [],

      containerWidth: 100,
      containerHeight: 100,

      // Some dialog show flags
      annotationDialog: {
        show: false,
        annotateRange: false,
        timelineId: null,
        timelineSegmentId: null,
      },

      // selection
      dragSelection: {
        x: null,
        start: null,
        end: null,
        dragging: false,
      },

      // Last updated timeline version
      lastTimestamp: 0,

      // Context
      segmentMenu: {
        show: false,
        x: null,
        y: null,
        selected: null,
      },
      timelineTooltip: {
        show: false,
        x: null,
        y: null,
        selected: null,
        label: null,
        enabled: false,
      },
      menu: {
        show: false,
        x: null,
        y: null,
        selected: null,
      },
      //segment_list
      timelineSegments: [],
    };
  },
  methods: {
    startDragging(event, x, time) {
      this.dragSelection.x = x;
      this.dragSelection.start = time;
      this.dragSelection.dragging = true;

      this.timelineStore.setSelectedTimeRangeStart(time);
      this.timelineStore.setSelectedTimeRangeEnd(null);
      event.stopPropagation();
    },
    moveDragging(event, x, time) {
      if (!this.dragSelection.dragging) {
        return;
      }
      if (Math.abs(x - this.dragSelection.x) < 2) {
        return;
      }

      // const segment = drawnTimeline.getSegmentOnPosition(x);
      // if (segment) {
      //   // this.timelineSegmentStore.addToSelection(segment.id);
      // }

      this.dragSelection.end = time;

      this.timelineStore.setSelectedTimeRangeEnd(time);

      event.stopPropagation();
    },
    endDragging(event, x, time) {
      this.dragSelection.dragging = false;
      if (Math.abs(x - this.dragSelection.x) < 2) {
        this.timelineStore.setSelectedTimeRangeEnd(null);
        return;
      }
      this.dragSelection.end = time;

      this.timelineStore.setSelectedTimeRangeEnd(time);
      event.stopPropagation();
    },

    getTimeline(timelineId) {
      var found = null;
      this.timelineObjects.forEach((timelineObject) => {
        if (timelineObject.timelineId === timelineId) {
          found = timelineObject;
        }
      });
      return found;
    },
    computeTimelineX() {
      return this.timeToX(this.startTime);
    },
    computeTimelineY(index) {
      return (
        (this.gap + this.timelineHeight) * index +
        this.scaleHeight +
        2 * this.gap
      );
    },
    async nodeOpenChanged(node) {
      // on a node is closed or open(node)
      await this.timelineStore.setCollapse({
        timelineId: node.id,
        collapse: !node.open,
      });
    },
    async change(node) {
      // after drop, only when the node position changed

      // set new order of timelines
      function timelineOrder(elem) {
        var hierarchy = [];
        elem.forEach((e) => {
          hierarchy.push(e.id);
          hierarchy.push.apply(hierarchy, timelineOrder(e.children));
        });
        return hierarchy;
      }

      let order = timelineOrder(this.timelineHierarchy);
      await this.timelineStore.setOrder({
        order: order,
      });

      // set new parent of node
      await this.timelineStore.setParent({
        timelineId: node.id,
        parentId: node.parent.id,
      });
    },
    draw() {
      this.drawTimelines();
      this.drawScale();
      this.drawTimeBar();
    },
    drawTimeBar() {
      if (this.timeBarsContainer) {
        this.app.stage.removeChild(this.timeBarsContainer);
      }

      this.timeBarsContainer = new PIXI.Container();
      this.timeBarsObjects = [];

      const x = this.timeToX(this.startTime);
      const y = this.gap;
      const width = this.timeToX(this.endTime) - x;
      const height = window.innerHeight;

      let timeline = new TimeBar(
        x,
        y,
        width,
        height,
        this.time,
        this.startTime,
        this.endTime
      );

      this.timeBarsContainer.addChild(timeline);
      this.timeBarsObjects.push(timeline);
      this.app.stage.addChild(this.timeBarsContainer);
    },
    drawScale() {
      if (this.timeScalesContainer) {
        this.app.stage.removeChild(this.timeScalesContainer);
      }

      this.timeScalesContainer = new PIXI.Container();
      this.timeScaleObjects = [];

      const x = this.timeToX(this.startTime);
      const y = this.gap;
      const width = this.timeToX(this.endTime) - x;
      const height = this.scaleHeight;

      let timeline = new TimeScale(
        x,
        y,
        width,
        height,
        this.startTime,
        this.endTime
      );

      this.timeScalesContainer.addChild(timeline);
      this.timeScaleObjects.push(timeline);
      this.app.stage.addChild(this.timeScalesContainer);
    },
    drawTimelines() {
      if (this.timelinesContainer) {
        this.app.stage.removeChild(this.timelinesContainer);
      }
      this.timelinesContainer = new PIXI.Container();
      this.timelineObjects = [];

      this.timelines.forEach((e, i) => {
        const x = this.timeToX(this.startTime);
        const y =
          (this.gap + this.timelineHeight) * i +
          this.scaleHeight +
          2 * this.gap;

        const timeline = this.drawTimeline(e);

        if (timeline) {
          timeline.x = x;
          timeline.y = y;
          this.timelinesContainer.addChild(timeline);
          this.timelineObjects.push(timeline);
        }
      });

      this.app.stage.addChild(this.timelinesContainer);
    },
    drawTimeline(timeline) {
      const width = this.timeToX(this.endTime) - this.timeToX(this.startTime);
      const height = this.timelineHeight;
      if (timeline.type == "ANNOTATION" || timeline.type == "TRANSCRIPT") {
        return this.drawAnnotationTimeline(timeline, width, height);
      } else if (timeline.type == "PLUGIN_RESULT") {
        return this.drawGraphicTimeline(timeline, width, height);
      } else {
        console.error(`Unknown timeline type ${timeline.type}`);
      }
      return null;
    },
    drawAnnotationTimeline(timeline, width, height) {

      const selection = this.selectedTimelineSegments
        .filter(
          (selectedTimelineSegment) =>
            timeline.id === selectedTimelineSegment.timeline_id
        )
        .map((s) => s.id);

      const timelineSegmentStore = useTimelineSegmentStore();
      const timelineSegmentAnnotationStore =
        useTimelineSegmentAnnotationStore();
      const annotationStore = useAnnotationStore();
      const annotationCategoryStore = useAnnotationCategoryStore();

      let segments = timelineSegmentStore.forTimeline(timeline.id);
      segments.forEach((s) => {
        let annotations = timelineSegmentAnnotationStore.forTimelineSegment(
          s.id
        );
        annotations.forEach((a) => {
          a.annotation = annotationStore.get(a.annotation_id);
        });
        annotations.forEach((a) => {
          a.category = annotationCategoryStore.get(a.category_id);
        });
        s.annotations = annotations;
      });

      timeline.segments = segments;

      let drawnTimeline = new AnnotationTimeline({
        timelineId: timeline.id,
        width: width,
        height: height,
        startTime: this.startTime,
        endTime: this.endTime,
        duration: this.duration,
        data: timeline,
        renderer: this.app.renderer,
        segmentSelection: selection,
      });
      drawnTimeline.interactive = true;
      drawnTimeline.buttonMode = true;
      drawnTimeline.on("rightdown", (ev) => {
        const point = this.mapToGlobal(ev.data.global);
        const x = ev.data.getLocalPosition(drawnTimeline).x;
        const segment = drawnTimeline.getSegmentOnPosition(x).segment;

        this.segmentMenu.show = true;
        this.segmentMenu.x = point.x;
        this.segmentMenu.y = point.y;
        this.segmentMenu.selected = segment.id;
        this.$nextTick(() => {
          this.showMenu = true;
          this.annotationDialog.timelineId = timeline.id;
          this.annotationDialog.timelineSegmentId = segment.id;
        });
        ev.stopPropagation();
      });
      drawnTimeline.on("click", (ev) => {
        const x = ev.data.getLocalPosition(drawnTimeline).x;
        const segment = drawnTimeline.getSegmentOnPosition(x);
        if (segment === null) {
          return;
        }
        if (!ev.data.originalEvent.ctrlKey) {
          this.timelineSegmentStore.clearSelection();
          this.timelineStore.clearSelection();
        }
        this.timelineStore.addToSelection(timeline.id);
        if (segment) {
          this.timelineSegmentStore.addToSelection(segment.segment.id);
        }
        const targetTime = this.xToTime(ev.data.global.x);
        this.playerStore.setTargetTime(targetTime);
        ev.stopPropagation();
      });

      drawnTimeline.on("mousedown", (ev) => {
        const x = ev.data.getLocalPosition(drawnTimeline).x;
        const time = drawnTimeline.xToTime(x);
        this.startDragging(ev, x, time);
      });
      drawnTimeline.on("mousemove", (ev) => {
        const x = ev.data.getLocalPosition(drawnTimeline).x;
        const time = drawnTimeline.xToTime(x);
        this.moveDragging(ev, x, time);
      });
      drawnTimeline.on("mouseup", (ev) => {
        const x = ev.data.getLocalPosition(drawnTimeline).x;
        const time = drawnTimeline.xToTime(x);
        this.endDragging(ev, x, time);
      });
      drawnTimeline.on("mouseupoutside", (ev) => {
        const x = ev.data.getLocalPosition(drawnTimeline).x;
        const time = drawnTimeline.xToTime(x);
        this.endDragging(ev, x, time);
      });

      drawnTimeline.on("pointerover", (ev) => {
        this.timelineTooltip.enabled = true;
        const x = ev.data.getLocalPosition(drawnTimeline).x;
        const segment = drawnTimeline.getSegmentOnPosition(x);
        if (segment === null) {
          return;
        }

          const tooltipPoint = {
            x: ev.data.global.x,
            y: ev.data.global.y,
          };
          const point = this.mapToGlobal(tooltipPoint);
          this.timelineTooltip.show = true;
          this.timelineTooltip.x = point.x;
          this.timelineTooltip.y = point.y;
          this.timelineTooltip.selected = segment.segment.id;

          const annotations = segment.segment.annotations.map((e) => {
            return e.annotation.name;
          });
        if (segment.segment.annotations.length > 0) {
          this.timelineTooltip.label = annotations.join("; ");
        } else {
          this.timelineTooltip.label = 'Segment ' + (segment.index + 1);
        }
        // ev.stopPropagation();
      });

      drawnTimeline.on("pointerout", () => {
        this.timelineTooltip.enabled = false;
        this.timelineTooltip.show = false;
        // ev.stopPropagation();
      });
      drawnTimeline.on("pointermove", (ev) => {
        if (this.timelineTooltip.enabled) {
          const localPosition = ev.data.getLocalPosition(drawnTimeline);
          const x = localPosition.x;
          if (localPosition.y < 0 || localPosition.y > drawnTimeline.height) {
            return;
          }
          const segment = drawnTimeline.getSegmentOnPosition(x);
          if (segment === null) {
            this.timelineTooltip.label = "";
            this.timelineTooltip.show = false;
            return;
          }

          this.timelineTooltip.show = true;
          const tooltipPoint = {
            x: ev.data.global.x,
            y: ev.data.global.y,
          };
          const point = this.mapToGlobal(tooltipPoint);

          this.timelineTooltip.x = point.x;
          this.timelineTooltip.y = point.y;
          const annotations = segment.segment.annotations.map((e) => {
            return e.annotation.name;
          });
          if (segment.segment.annotations.length <= 0) {
            this.timelineTooltip.label = 'Segment ' + (segment.index + 1);
          } else {
            this.timelineTooltip.label = annotations.join("; ");
          }
        }
        // ev.stopPropagation();
      });
      return drawnTimeline;
    },
    drawGraphicTimeline(timeline, width, height) {
      const pluginRunResultStore = usePluginRunResultStore();

      let drawnTimeline = null;
      if ("plugin_run_result_id" in timeline) {
        const result = pluginRunResultStore.get(timeline.plugin_run_result_id);

        if (result === undefined) {
          return null;
        } else {
          timeline.plugin = { data: result.data, type: result.type };
        }
        if (timeline.visualization == "COLOR") {
          drawnTimeline = new ColorTimeline({
            timelineId: timeline.id,
            width: width,
            height: height,
            startTime: this.startTime,
            endTime: this.endTime,
            duration: this.duration,
            data: timeline.plugin.data,
            renderer: this.app.renderer,
          });
        }
        if (timeline.visualization == "SCALAR_COLOR") {
          drawnTimeline = new ScalarColorTimeline({
            timelineId: timeline.id,
            width: width,
            height: height,
            startTime: this.startTime,
            endTime: this.endTime,
            duration: this.duration,
            data: timeline.plugin.data,
            renderer: this.app.renderer,
            colormap: timeline.colormap,
            colormapInverse: timeline.colormap_inverse,
          });
        }
        if (timeline.visualization == "SCALAR_LINE") {
          drawnTimeline = new ScalarLineTimeline({
            timelineId: timeline.id,
            width: width,
            height: height,
            startTime: this.startTime,
            endTime: this.endTime,
            duration: this.duration,
            data: timeline.plugin.data,
            renderer: this.app.renderer,
            colormap: timeline.colormap,
            colormapInverse: timeline.colormap_inverse,
          });
        }
        if (timeline.visualization == "HIST") {
          drawnTimeline = new HistTimeline({
            timelineId: timeline.id,
            width: width,
            height: height,
            startTime: this.startTime,
            endTime: this.endTime,
            duration: this.duration,
            data: timeline.plugin.data,
            renderer: this.app.renderer,
            colormap: timeline.colormap,
            colormapInverse: timeline.colormap_inverse,
          });
        }
      }
      if (drawnTimeline) {
        drawnTimeline.interactive = true;
        drawnTimeline.buttonMode = true;
        drawnTimeline.on("click", (ev) => {
          if (!ev.data.originalEvent.ctrlKey) {
            this.timelineSegmentStore.clearSelection();
            this.timelineStore.clearSelection();
          }
          this.timelineStore.addToSelection(timeline.id);
          const targetTime = this.xToTime(ev.data.global.x);
          this.playerStore.setTargetTime(targetTime);
          ev.stopPropagation();
        });
      }
      return drawnTimeline;
    },
    addSegmentSelection(selectedTimelineSegments) {
      if (
        selectedTimelineSegments &&
        selectedTimelineSegments.length > 0 &&
        this.timelineObjects &&
        this.timelineObjects.length > 0
      ) {
        selectedTimelineSegments.forEach((selectedTimelineSegment) => {
          this.timelineObjects
            .filter(
              (timelineObject) =>
                timelineObject.timelineId ===
                selectedTimelineSegment.timeline_id
            )
            .filter(
              (timelineObject) =>
                typeof timelineObject.addSegmentSelection === "function"
            )
            .forEach((timelineObject) => {
              timelineObject.addSegmentSelection(selectedTimelineSegment.id);
            });
        });
      }
    },
    removeSegmentSelection(selectedTimelineSegments) {
      if (
        selectedTimelineSegments &&
        selectedTimelineSegments.length > 0 &&
        this.timelineObjects &&
        this.timelineObjects.length > 0
      ) {
        selectedTimelineSegments.forEach((selectedTimelineSegment) => {
          this.timelineObjects
            .filter(
              (timelineObject) =>
                timelineObject.timelineId ===
                selectedTimelineSegment.timeline_id
            )
            .filter(
              (timelineObject) =>
                typeof timelineObject.removeSegmentSelection === "function"
            )
            .forEach((timelineObject) => {
              timelineObject.removeSegmentSelection(selectedTimelineSegment.id);
            });
        });
      }
    },
    timeToX(time) {
      return this.timeScale * (time - this.startTime);
    },
    xToTime(x) {
      return x / this.timeScale + this.startTime;
    },
    mapToGlobal(point) {
      const screenRect = this.app.screen;
      const canvasRect = this.$refs.canvas.getBoundingClientRect();

      const windowsX =
        (point.x / screenRect.width) * canvasRect.width + canvasRect.x;
      const windowsY =
        (point.y / screenRect.height) * canvasRect.height + canvasRect.y;

      return { x: windowsX, y: windowsY };
    },
    onAnnotateSelection() {
      this.annotationDialog.show = true;
      this.annotationDialog.annotateRange = false;
    },
    onAnnotateSelectionRange() {
      this.annotationDialog.show = true;
      this.annotationDialog.annotateRange = true;
    },
    onMergeSelection() {},
    onMergeSelectionRange() {},
    onSplitSegment() {
      this.timelineSegmentStore.split({
        timelineSegmentId: this.segmentMenu.selected,
        time: this.playerStore.targetTime,
      });
    },
    onMergeSegments() {
      const timelineSegmentIds = this.timelineSegmentStore.selected.map(
        (e) => e.id
      );
      this.timelineSegmentStore.merge({
        timelineSegmentIds: timelineSegmentIds,
      });
    },
    onMergeSegmentsLeft() {
      if (this.timelineSegmentStore.selected.length <= 0) {
        return;
      }
      const timelineSegmentId =
        this.timelineSegmentStore.selected[
          this.timelineSegmentStore.selected.length - 1
        ].id;
      const previousTimelineSegment =
        this.timelineSegmentStore.getPreviousOnTimeline(timelineSegmentId);
      if (previousTimelineSegment) {
        this.timelineSegmentStore.merge({
          timelineSegmentIds: [timelineSegmentId, previousTimelineSegment.id],
        });
      }
    },
    onMergeSegmentsRight() {
      if (this.timelineSegmentStore.selected.length <= 0) {
        return;
      }
      const timelineSegmentId =
        this.timelineSegmentStore.selected[
          this.timelineSegmentStore.selected.length - 1
        ].id;
      const nextTimelineSegment =
        this.timelineSegmentStore.getNextOnTimeline(timelineSegmentId);
      if (nextTimelineSegment) {
        this.timelineSegmentStore.merge({
          timelineSegmentIds: [timelineSegmentId, nextTimelineSegment.id],
        });
      }
    },
  },
  computed: {
    duration() {
      let duration = this.playerStore.videoDuration;
      return duration;
    },
    isLoading() {
      let isLoading = this.videoStore.isLoading;
      return isLoading;
    },
    startTime() {
      let start = this.playerStore.selectedTimeRange.start;
      return start;
    },
    endTime() {
      let end = this.playerStore.selectedTimeRange.end;
      return end;
    },
    timelines() {
      let timelines = this.timelineStore.all;
      return timelines;
    },
    timelinesAdded() {
      let timelines = this.timelineStore.added;
      return timelines;
    },
    timelinesChanged() {
      let timelines = this.timelineStore.changed;
      return timelines;
    },
    timelinesDeleted() {
      let timelines = this.timelineStore.deleted;
      return timelines;
    },
    selectedTimelineSegments() {
      return this.timelineSegmentStore.selected;
    },
    timeScale() {
      return this.containerWidth / (this.endTime - this.startTime);
    },
    computedHeight() {
      return (
        this.timelines.length * (this.timelineHeight + this.gap) +
        this.scaleHeight +
        3 * this.gap
      );
    },
    time() {
      return this.playerStore.currentTime;
    },
    ...mapStores(
      useTimelineStore,
      usePlayerStore,
      useVideoStore,
      useTimelineSegmentStore
    ),
  },
  watch: {
    isLoading(newValue) {
      if (newValue === false) {
        this.enabled = true;
      }
    },
    timelines(values) {
      function findChildren(elem, parent) {
        let hierarchy = [];
        elem.sort((a,b) => a.order > b.order).forEach((e) => {
          if (e.parent_id == parent) {
            let children = findChildren(elem, e.id);
            hierarchy.push({
              id: e.id,
              text: e.name,
              children: children,
              type: e.type,
              open: !e.collapse,
            });
          }
        });
        return hierarchy;
      }
      this.timelineHierarchy = findChildren(values, null);
    },
    selectedTimelineSegments(newSelection, oldSelection) {
      this.removeSegmentSelection(oldSelection);
      this.addSegmentSelection(newSelection);
    },
  },
  mounted() {
    this.containerWidth = this.$refs.container.clientWidth;
    this.app = new PIXI.Application({
      width: this.containerWidth,
      height: this.containerHeight,
      // antialias: true,
      backgroundAlpha: 0.0,
      view: this.$refs.canvas,
      resizeTo: this.$refs.canvas,
    });

    this.$refs.canvas.addEventListener("contextmenu", (e) => {
      e.preventDefault();
    });

    // generate bitmapfont
    generateFont();

    this.app.ticker.add(() => {
      if (!this.enabled) {
        return;
      }
      // TODO improve this part
      if ("container" in this.$refs && this.$refs.container) {
        if (this.$refs.container.clientWidth != this.containerWidth) {
          this.containerWidth = this.$refs.container.clientWidth;
          this.draw();
        }
        if (this.computedHeight != this.containerHeight) {
          this.containerHeight = this.computedHeight;
          this.$refs.container.style.height = this.computedHeight;
          this.$refs.canvas.height = this.computedHeight;
          this.app.resize();
          this.draw();
        }
      }

      let latestTimestamp = -1;
      // handle timeline deletion
      this.timelinesDeleted.forEach((data) => {
        const [date, id] = data;

        if (date <= this.lastTimestamp) {
          return;
        }
        if (date > latestTimestamp) {
          latestTimestamp = date;
        }
        const timelineObject = this.getTimeline(id);
        if (timelineObject) {
          this.timelinesContainer.removeChild(timelineObject);
          const index = this.timelineObjects.indexOf(timelineObject);
          if (index > -1) {
            this.timelineObjects.splice(index, 1);
          }
        }
      });

      // handle timeline added
      this.timelinesAdded.forEach((data) => {
        const [date, timeline] = data;

        if (date <= this.lastTimestamp) {
          return;
        }
        const timelineObject = this.getTimeline(timeline.id);
        if (!timelineObject) {
          const newTimelineObject = this.drawTimeline(timeline);
          if (!newTimelineObject) {
            return;
          }
          this.timelinesContainer.addChild(newTimelineObject);
          this.timelineObjects.push(newTimelineObject);
          // we don't set x and y because we will move it at the end
        }

        if (date > latestTimestamp) {
          latestTimestamp = date;
        }
      });

      // handle timeline change
      this.timelinesChanged.forEach((data) => {
        const [date, timeline] = data;

        if (date <= this.lastTimestamp) {
          return;
        }
        const timelineObject = this.getTimeline(timeline.id);

        if (timelineObject) {
          this.timelinesContainer.removeChild(timelineObject);
          const index = this.timelineObjects.indexOf(timelineObject);
          if (index > -1) {
            this.timelineObjects.splice(index, 1);
          }
        }
        const newTimelineObject = this.drawTimeline(timeline);
        if (!newTimelineObject) {
          return;
        }
        this.timelinesContainer.addChild(newTimelineObject);
        this.timelineObjects.push(newTimelineObject);
        // we don't set x and y because we will move it at the end

        if (date > latestTimestamp) {
          latestTimestamp = date;
        }
      });
      // we have done all updates until this point
      if (latestTimestamp > 0) {
        this.lastTimestamp = latestTimestamp;
      }

      // update order and visible of all objects
      let skipped = 0;
      this.timelines
        .sort((a, b) => a.order - b.order)
        .forEach((timeline, i) => {
          const timelineObject = this.getTimeline(timeline.id);
          if (timelineObject) {
            timelineObject.y = this.computeTimelineY(i - skipped);
            if (!timeline.visible) {
              skipped += 1;
            }
            timelineObject.visible = timeline.visible;
          }
        });

      const rescale = false;
      // update all time position if there is something to update
      this.timelineObjects.forEach((e) => {
        if (e.startTime !== this.startTime || rescale) {
          e.startTime = this.startTime;
        }
      });
      this.timeScaleObjects.forEach((e) => {
        if (e.startTime !== this.startTime || rescale) {
          e.startTime = this.startTime;
        }
      });
      this.timeBarsObjects.forEach((e) => {
        if (e.startTime !== this.startTime || rescale) {
          e.startTime = this.startTime;
        }
      });
      this.timelineObjects.forEach((e) => {
        if (e.endTime !== this.endTime || rescale) {
          e.endTime = this.endTime;
        }
      });
      this.timeScaleObjects.forEach((e) => {
        if (e.endTime !== this.endTime || rescale) {
          e.endTime = this.endTime;
        }
      });
      this.timeBarsObjects.forEach((e) => {
        if (e.endTime !== this.endTime || rescale) {
          e.endTime = this.endTime;
        }
      });
      this.timeBarsObjects.forEach((e) => {
        if (e.time !== this.time || rescale) {
          e.time = this.time;
        }
      });

      // update height
      this.timeBarsObjects.forEach((e) => {
        if (e.height !== this.computedHeight || rescale) {
          e.height = this.computedHeight;
        }
      });
      // update selection
      this.timeBarsObjects.forEach((e) => {
        const start = this.timelineStore.timelineSelectedTimeRange.start;
        const end = this.timelineStore.timelineSelectedTimeRange.end;
        if (e.selectedRangeStart !== start || e.selectedRangeEnd !== end) {
          e.selectedRangeStart = start;
          e.selectedRangeEnd = end;
        }
      });
    });
    // this.draw();
  },
  components: {
    ModalRenameTimeline,
    ModalCopyTimeline,
    ModalDeleteTimeline,
    ModalExportResult,
    ModalCreateTimeline,
    ModalVisualizationTimeline,
    ModalImportTimeline,
    DraggableTree,
    ModalTimelineSegmentAnnotate,
  },
};
</script>

<style>
.draggable-placeholder-inner {
  border: 1px solid #ae1313;
  background: #ae131377;
}
</style>