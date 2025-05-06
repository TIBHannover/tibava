import * as PIXI from "pixi.js";
import { DropShadowFilter } from "pixi-filters";


export class Timeline extends PIXI.Container {
    constructor({
        timelineId,
        width,
        height,
        startTime = 0,
        endTime = 10,
        duration = 10,
        fill = 0xffffff,
    }) {
        super();
        this.pWidth = width;
        this.pHeight = height;
        this.pStartTime = startTime;
        this.pEndTime = endTime;
        this.pDuration = duration;
        this.pTimelineId = timelineId;

        this.pRangeSelection = null
        this.pRangeSelectedColor = 0xd99090;

        // console.log(this.timeScale)
        // console.log(this.timeToX(this.pEndTime))
        // draw canvas
        this.pRect = new PIXI.Graphics()
            .beginFill(fill)
            .drawRoundedRect(0, 0, width, height, 5);

        // set mask to visible area
        this.pMask = new PIXI.Graphics()
            .beginFill(0xffffff)
            .drawRoundedRect(0, 0, width, height, 5);
        this.pRect.mask = this.pMask;
        this.pRect.addChild(this.pMask);

        let shadow = new DropShadowFilter();
        shadow.color = 0x0000;
        shadow.distance = 2;
        shadow.alpha = 0.4;
        shadow.rotation = 90;
        shadow.blur = 1;
        this.pRect.filters = [shadow];
        super.addChild(this.pRect);
    }

    selectRange(start, end) {
        if (this.pRangeSelection) {
            this.pRangeSelection.destroy()
            this.pRangeSelection = null;
        }

        const selectionRect = new PIXI.Graphics();

        const x = this.timeToX(start);

        const width = this.timeToX(end) - this.timeToX(start);
        const height = this.pHeight;
        selectionRect.lineStyle(2, this.pRangeSelectedColor, 1);

        selectionRect.beginFill(this.pRangeSelectedColor, 0.2);
        selectionRect.drawRoundedRect(0, 0, width, height, 1);
        selectionRect.x = x

        this.pRangeSelection = selectionRect;
        this.addChild(selectionRect)
    }
    removeSelectRange() {
        if (this.pRangeSelection) {
            this.pRangeSelection.destroy()
            this.pRangeSelection = null;
        }
    }

    addChild(child) {
        this.pRect.addChild(child);
    }

    timeToX(time) {
        return this.timeScale * (time - this.pStartTime);
    }
    xToTime(xPos) {
        return xPos / this.timeScale + this.pStartTime;
    }
    scaleContainer() { }
    get timeScale() {
        return this.pWidth / (this.pEndTime - this.pStartTime);
    }
    get timelineId() {
        return this.pTimelineId;
    }
    set startTime(time) {
        this.pStartTime = time;
        this.scaleContainer();
    }
    get startTime() {
        return this.pStartTime;
    }
    set endTime(time) {
        this.pEndTime = time;
        this.scaleContainer();
    }
    get endTime() {
        return this.pEndTime;
    }

}