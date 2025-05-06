import * as PIXI from "pixi.js";

import { Timeline } from "./timeline";

import { resampleApprox, scalarToHex, getMax, getMin } from "./utils";

export class ScalarColorTimeline extends Timeline {
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
    colormap = null,
    colormapInverse = false,
  }) {
    super({ timelineId, width, height, startTime, endTime, duration, fill });

    this.pData = data;
    if (!colormap) {
      this.pColormap = "TIBReds"
    }
    else {
      this.pColormap = colormap;
    }

    this.pColormapInverse = colormapInverse;

    this.pDataMinTime = getMin(data.time);
    this.pDataMaxTime = getMax(data.time);


    this.pResolution = resolution;
    this.pOversampling = oversampling;
    this.pRenderer = renderer;

    this.cRects = this.renderGraph();

    this.addChild(this.cRects);

    this.scaleContainer();
  }

  renderGraph() {
    const renderWidth = this.pResolution;
    const r = renderWidth / this.pDuration;

    const brt = new PIXI.BaseRenderTexture({
      width: renderWidth,
      height: this.pHeight,
      // PIXI.SCALE_MODES.NEAREST,
      scaleMode: PIXI.SCALE_MODES.LINEAR,

      resolution: 1,
    });
    const rt = new PIXI.RenderTexture(brt);

    const sprite = new PIXI.Sprite(rt);

    let colorRects = new PIXI.Graphics();
    // fill with nothing
    let color = scalarToHex(0);
    colorRects.beginFill(color);
    colorRects.drawRect(0, 0, renderWidth, this.pHeight);

    const targetSize = this.pOversampling * this.pResolution;
    const y = resampleApprox({ data: this.pData.y, targetSize: targetSize });
    const times = resampleApprox({
      data: this.pData.time,
      targetSize: targetSize,
    });

    const deltaTime =
      (this.pData.delta_time * this.pData.time.length) / times.length;
    // console.log(deltaTime)
    // console.log(this.pData.delta_time)
    times.forEach((t, i) => {
      // if (i > 0) {
      //   return
      // }
      // console.log('##############')
      // console.log(t)
      // console.log(y[i])
      // console.log(this.pData.delta_time)
      // console.log(deltaTime)

      let color = scalarToHex(y[i], this.pColormapInverse, this.pColormap);
      colorRects.beginFill(color);
      // colorRects.drawRect(r * t, 0, r * deltaTime, this.pHeight);
      colorRects.drawRect(
        Math.max(0, r * (t - deltaTime / 2)),
        0,
        r * deltaTime,
        this.pHeight
      );

    });

    this.pRenderer.render(colorRects, rt);
    return sprite;
  }

  scaleContainer() {
    if (this.cRects) {
      const width =
        this.timeToX(this.pDuration) - this.timeToX(0);
      const x = this.timeToX(0);
      this.cRects.x = x;
      this.cRects.width = width;
    }
  }
}
