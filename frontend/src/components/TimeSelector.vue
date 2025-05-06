<template>
  <div ref="container" style="width: 100%">
    <canvas :style="canvasStyle" ref="canvas" resize> </canvas>
  </div>
</template>

<script>
import TimeMixin from "../mixins/time";
import paper from "paper";

import { mapStores } from "pinia";
import { usePlayerStore } from "@/store/player";

export default {
  mixins: [TimeMixin],
  props: {
    width: {
      default: "100%",
    },
    height: {
      default: "60",
    },
    radius: {
      type: Number,
      default: 5,
    },
  },
  data() {
    return {
      canvasStyle: {
        height: this.height,
        width: this.width,
      },
      canvasWidth: null,
      canvasHeight: null,
      containerWidth: null,
      containerHeight: null,

      canvas: null,
      scope: null,
      tool: null,
      redraw: false,

      hiddenStartTime: 0,
      hiddenEndTime: 0,
      minTime: 1.0,

      mainStrokes: null,
      otherStrokes: null,
      textGroup: null,

      handleGroup: null,
      handleLeft: null,
      handleRight: null,
      handleBar: null,
    };
  },
  methods: {
    draw() {
      this.canvas.height = this.height;
      var desiredWidth = this.$refs.container.clientWidth; // For instance: $(window).width();

      this.containerWidth = this.$refs.container.clientWidth;
      this.containerHeight = this.$refs.container.clientHeight;
      this.canvas.width = desiredWidth;

      this.scope.view.viewSize = new paper.Size(
        this.canvas.width,
        this.canvas.height
      );
      this.scope.view.draw();

      this.canvasWidth = this.scope.view.size.width;
      this.canvasHeight = this.scope.view.size.height;
      this.timeScale = this.scope.view.size.width / this.duration;

      if (isNaN(this.timeScale)) {
        return;
      }

      this.tool = new paper.Tool();

      this.drawScale();
      this.drawSelection();
      this.scope.view.draw();
    },

    drawScale() {
      if (this.scaleLayer) {
        this.scaleLayer.removeChildren();
      }
      this.scope.activate();
      this.scaleLayer = new paper.Layer();
      
      // determine optimal scaling
      const timeline_options = [30, 60, 150, 300, 600];
      var time_interval_length_in_seconds = this.duration / 10;
      var diff = 9999999;
      var best_option = 30;

      for (const option of timeline_options) {
        if (Math.abs(time_interval_length_in_seconds - option) < diff)
        {
          diff = Math.abs(time_interval_length_in_seconds - option);
          best_option = option;
        }
      }
      time_interval_length_in_seconds = best_option;
      
      let mainTimeStrokes = parseInt(this.duration / time_interval_length_in_seconds) + 1;
      let minorTimeStrokes = 4;
      let timestamps = this.linspace(0, mainTimeStrokes, time_interval_length_in_seconds);
      let mainStrokes = [];
      timestamps.forEach((time) => {
        let path = new paper.Path();

        let x = this.timeToX(time);
        path.add(new paper.Point(x, 10), new paper.Point(x, 35));
        mainStrokes.push(path);
      });
      this.mainStrokes = new paper.Group(mainStrokes);
      this.mainStrokes.strokeColor = "black";
      this.mainStrokes.strokeWidth = 2;

      timestamps.pop();
      let textList = [];
      timestamps.forEach((time) => {
        let x = this.timeToX(time);
        let text = new paper.PointText(new paper.Point(x, 50));
        text.content = this.get_timecode(time, 0);
        textList.push(text);
      });
      this.textGroup = new paper.Group(textList);
      this.textGroup.style = {
        fontFamily: "Courier New",
        fontSize: 10,
        fillColor: "black",
      };

      let otherTimestamps = this.linspace(0, mainTimeStrokes * minorTimeStrokes, time_interval_length_in_seconds/minorTimeStrokes);
      let otherStrokes = [];
      otherTimestamps.forEach((time) => {
        let path = new paper.Path();

        let x = this.timeToX(time);
        path.add(new paper.Point(x, 25), new paper.Point(x, 30));
        otherStrokes.push(path);
      });
      this.otherStrokes = new paper.Group(otherStrokes);
      this.otherStrokes.strokeColor = "black";
    },

    drawSelection() {
      if (this.selectionLayer) {
        this.selectionLayer.removeChildren();
      }
      this.scope.activate();
      this.selectionLayer = new paper.Layer();
      let rectangle = new paper.Rectangle(
        new paper.Point(this.timeToX(this.hiddenStartTime), 5),
        new paper.Point(this.timeToX(this.hiddenEndTime), this.canvasHeight - 5)
      );
      let radius = new paper.Size(this.radius, this.radius);
      let path = new paper.Path.Rectangle(rectangle, radius);
      path.fillColor = "#ae131377";

      this.handleBar = path;

      //handle
      let handleRadius = new paper.Size(this.radius, this.radius);
      let handleLeftRect = new paper.Rectangle(
        new paper.Point(this.timeToX(this.hiddenStartTime) - 5, 10),
        new paper.Point(
          this.timeToX(this.hiddenStartTime) + 5,
          this.canvasHeight - 10
        )
      );
      let handleLeft = new paper.Path.Rectangle(handleLeftRect, handleRadius);
      handleLeft.fillColor = "#ae1313ff";

      this.handleLeft = handleLeft;

      let handleRightRect = new paper.Rectangle(
        new paper.Point(this.timeToX(this.hiddenEndTime) - 5, 10),
        new paper.Point(
          this.timeToX(this.hiddenEndTime) + 5,
          this.canvasHeight - 10
        )
      );
      let handleRight = new paper.Path.Rectangle(handleRightRect, handleRadius);
      handleRight.fillColor = "#ae1313ff";

      this.handleRight = handleRight;
      this.handleGroup = new paper.Group([path, handleLeft, handleRight]);

      let self = this;
      handleLeft.onMouseDrag = (event) => {
        let deltaTime = self.xToTime(event.delta.x);

        if (deltaTime > 0) {
          self.hiddenStartTime = Math.min(
            self.hiddenStartTime + deltaTime,
            self.hiddenEndTime - self.minTime
          );
        } else {
          self.hiddenStartTime = Math.max(self.hiddenStartTime + deltaTime, 0);
        }
        self.onSelectionChange();
      };

      handleRight.onMouseDrag = (event) => {
        let deltaTime = self.xToTime(event.delta.x);

        if (deltaTime < 0) {
          self.hiddenEndTime = Math.max(
            self.hiddenEndTime + deltaTime,
            self.hiddenStartTime + self.minTime
          );
        } else {
          self.hiddenEndTime = Math.min(
            self.hiddenEndTime + deltaTime,
            self.duration
          );
        }
        self.onSelectionChange();
      };

      path.onMouseDrag = (event) => {
        //timespan should be const
        const timeSpan = self.hiddenEndTime - self.hiddenStartTime;
        let deltaTime = self.xToTime(event.delta.x);
        if (deltaTime > 0) {
          self.hiddenEndTime = Math.min(
            self.hiddenEndTime + deltaTime,
            self.duration
          );
          self.hiddenStartTime = self.hiddenEndTime - timeSpan;
        } else {
          self.hiddenStartTime = Math.max(self.hiddenStartTime + deltaTime, 0);
          self.hiddenEndTime = self.hiddenStartTime + timeSpan;
        }
        self.onSelectionChange();
      };
    },

    linspace(startValue, stopValue, step) {
      var arr = [];
      for (var i = 0; i <= stopValue; i++) {
        arr.push(startValue + step * i);
      }
      return arr;
    },
    //  map time to x and x to time
    timeToX(time) {
      return this.timeScale * time;
    },
    xToTime(x) {
      return x / this.timeScale;
    },
    // some event handler
    onResize() {
      this.$nextTick(() => {
        this.draw();
      });
    },
    onSelectionChange() {
      let posStart = this.timeToX(this.hiddenStartTime);
      let posEnd = this.timeToX(this.hiddenEndTime);
      this.handleLeft.position.x = posStart;
      this.handleRight.position.x = posEnd;
      this.handleBar.segments[0].point.x = posStart + this.radius;
      this.handleBar.segments[1].point.x = posStart;
      this.handleBar.segments[2].point.x = posStart;
      this.handleBar.segments[3].point.x = posStart + this.radius;

      this.handleBar.segments[4].point.x = posEnd - this.radius;
      this.handleBar.segments[5].point.x = posEnd;
      this.handleBar.segments[6].point.x = posEnd;
      this.handleBar.segments[7].point.x = posEnd - this.radius;
    },
  },
  watch: {
    startTime(newValue) {
      this.hiddenStartTime = newValue;
      this.draw();
    },
    endTime(newValue) {
      this.hiddenEndTime = newValue;
      this.draw();
    },
    duration(){
      this.hiddenStartTime = this.startTime
      this.hiddenEndTime = this.endTime
      this.draw();
    },
    hiddenStartTime() {
      this.$nextTick(() => {
      this.playerStore.setSelectedTimeRangeStart(this.hiddenStartTime)
        this.$emit("update:startTime", this.hiddenStartTime);
      });
    },
    hiddenEndTime() {
      this.$nextTick(() => {
      this.playerStore.setSelectedTimeRangeEnd(this.hiddenEndTime);
        this.$emit("update:endTime", this.hiddenEndTime);
      });
    },
  },
  computed: {
    duration(){
      return this.playerStore.videoDuration;
    },
    currentTime(){
      return this.playerStore.currentTime;
    },
    startTime(){
      return this.playerStore.selectedTimeRange.start;
    },
    endTime(){
      return this.playerStore.selectedTimeRange.end;
    },
    ...mapStores(usePlayerStore),
  },
  mounted() {
    this.canvas = this.$refs.canvas;

    this.scope = new paper.PaperScope();
    this.scope.setup(this.canvas);

    let self = this;

    this.scope.view.onFrame = () => {
      if (
        self.$refs.container.clientWidth !== self.containerWidth ||
        self.$refs.container.clientHeight !== self.containerHeight
      ) {
        clearTimeout(self.redraw);
        self.redraw = setTimeout(self.onResize(), 100);
      }
    };

    this.scope.view.onResize = () => {
      clearTimeout(self.redraw);
      self.redraw = setTimeout(self.onResize(), 100);
    };

    this.draw();
  },
};
</script>
