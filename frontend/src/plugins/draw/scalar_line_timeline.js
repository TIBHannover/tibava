import * as PIXI from "pixi.js";

import { Timeline } from "./timeline";
// import * as tf from '@tensorflow/tfjs';
import { resampleApprox, getMax, getMin } from "./utils"

export class ScalarLineTimeline extends Timeline {
  constructor({
    timelineId,
    width = 10,
    height = 10,
    startTime = 0,
    endTime = 10,
    duration = 10,
    data = null,
    fill = 0xffffff,
    renderer = null,
    resolution = 1024,
    oversampling = 1,
  }) {
    super({ timelineId, width, height, startTime, endTime, duration, fill });

    this.pData = data;

    this.pDataMinTime = getMin(data.time);
    this.pDataMaxTime = getMax(data.time);

    this.pResolution = resolution
    this.pOversampling = oversampling
    this.pRenderer = renderer

    this.path = this.renderGraph();

    // this.path.y = this.pHeight / 2;

    this.addChild(this.path);

    this.scaleContainer();
  }

  renderGraph() {
    const renderWidth = this.pResolution;
    const r = renderWidth / this.pDuration

    const brt = new PIXI.BaseRenderTexture({
      width: renderWidth,
      height: this.pHeight,
      // PIXI.SCALE_MODES.NEAREST,
      scaleMode: PIXI.SCALE_MODES.LINEAR,

      resolution: 1
    });
    const rt = new PIXI.RenderTexture(brt);

    const sprite = new PIXI.Sprite(rt);

    const path = new PIXI.Graphics().lineStyle(1, 0xae1313, 1);


    const targetSize = this.pOversampling * this.pResolution
    const y = resampleApprox({ data: this.pData.y, targetSize: targetSize })
    const times = resampleApprox({ data: this.pData.time, targetSize: targetSize })

    this.pData.delta_time * this.pData.time.length / times.length
    times.forEach((t, i) => {
      if (i == 0) {
        path.moveTo(
          r * t,
          this.pHeight - y[i] * this.pHeight
        );
      }
      path.lineTo(
        r * t,
        this.pHeight - y[i] * this.pHeight
      );
    });

    this.pRenderer.render(path, rt);
    return sprite;
  }

  scaleContainer() {
    if (this.path) {
      const width = this.timeToX(this.pDuration) - this.timeToX(0);
      const x = this.timeToX(0);
      this.path.x = x;
      this.path.width = width;
    }
  }
}
