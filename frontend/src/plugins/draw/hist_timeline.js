import * as PIXI from "pixi.js";

import { Timeline } from "./timeline";
import { resampleApprox, scalarToRGB } from "./utils"

export class HistTimeline extends Timeline {
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

        this.pDataMinTime = Math.min(...data.time);
        this.pDataMaxTime = Math.max(...data.time);


        this.pResolution = resolution
        this.pOversampling = oversampling
        this.pRenderer = renderer

        this.cRects = this.renderGraph();

        this.addChild(this.cRects);

        this.scaleContainer();
    }

    renderGraph() {
        const renderWidth = this.pResolution;

        const brt = new PIXI.BaseRenderTexture({
            width: renderWidth,
            height: this.pHeight,
            // PIXI.SCALE_MODES.NEAREST,
            scaleMode: PIXI.SCALE_MODES.LINEAR,

            resolution: 1
        });
        new PIXI.RenderTexture(brt);

        // const sprite = new PIXI.Sprite(rt);

        const targetSize = this.pOversampling * this.pResolution
        const hist = resampleApprox({ data: this.pData.hist, targetSize: targetSize })

        const width = hist.length
        const height = hist[0].length
        const flatdata = new Array(hist.length * hist[0].length)
        hist.forEach((element, x) => {
            element.forEach((e, y) => {
                flatdata[y * width + x] = e
            });
        });

        const data = new Uint8Array(flatdata.map((value) => { return scalarToRGB(value, this.pColormapInverse, this.pColormap) }).flat())
        const bt = new PIXI.Texture(new PIXI.BaseTexture(new PIXI.BufferResource(data, { width: width, height: height })));
        // console.log(bt)

        const sprite = new PIXI.Sprite(bt);
        // console.log(sprite)
        // console.log(data)
        // times.forEach((t, i) => {
        //     hist[i].forEach((v, j) => {
        //         const num_hist = hist[i].length;
        //         const startY = this.pHeight * (j / num_hist);
        //         const stopY = this.pHeight * ((j + 1) / num_hist);
        //         let color = scalarToHex(hist[i][j], false, this.pColormap);
        //         colorRects.beginFill(color);
        //         colorRects.drawRect(r * (t + this.pData.delta_time), startY, r * t, stopY);
        //     });
        // });

        // this.pRenderer.render(colorRects, rt);
        return sprite;
    }

    scaleContainer() {
        if (this.cRects) {
            const width =
                this.timeToX(this.pData.time[this.pData.time.length - 1]) -
                this.timeToX(this.pData.time[0]);
            const x = this.timeToX(this.pData.time[0]);
            this.cRects.x = x;
            this.cRects.width = width;
        }
    }
}
