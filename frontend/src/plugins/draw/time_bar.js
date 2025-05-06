import * as PIXI from "pixi.js";
import { DropShadowFilter } from "pixi-filters";

export class TimeBar extends PIXI.Container {
    constructor(x, y, width, height, time = 0, startTime = 0, endTime = 10) {
        super();
        this.pX = x;
        this.pY = y;
        this.pWidth = width;
        this.pHeight = height;
        this.pTime = time;
        this.pStartTime = startTime;
        this.pEndTime = endTime;
        this.pBar = null

        this.pRangeSelection = null
        this.pRangeSelectedColor = 0xd99090;

        const bar = this.renderBar()


        const timeX = this.timeToX(time);
        bar.x = timeX;
        bar.y = 25;
        this.pBar = bar
        this.addChild(bar);
    }
    renderBar() {
        const handleWidth = 10;
        const handleHeight = 10;

        const bar = new PIXI.Graphics()
            .lineStyle(1, 0xae1313, 1)
            .beginFill(0xae1313)
            .moveTo(0, this.pHeight - 25)
            .lineTo(0, handleHeight)
            .lineTo(handleWidth, 0)
            .lineTo(-handleWidth, 0)
            .lineTo(0, handleHeight)
            .closePath()
            .endFill();

        let shadow = new DropShadowFilter();
        shadow.color = 0x0000;
        shadow.distance = 2;
        shadow.alpha = 0.4;
        shadow.rotation = 90;
        shadow.blur = 1;
        bar.filters = [shadow];
        return bar
    }
    get timeScale() {
        return this.pWidth / (this.pEndTime - this.pStartTime);
    }
    timeToX(time) {
        return this.pX + this.timeScale * (time - this.pStartTime);
    }
    scaleSegment() {
        this.pBar.x = this.timeToX(this.pTime);
    }
    selectRange(start, end) {
        if (this.pRangeSelection) {
            this.pRangeSelection.destroy()
            this.pRangeSelection = null;
        }

        if (start === null || end === null) {
            return
        }

        const selectionRect = new PIXI.Graphics();

        const x = this.timeToX(start);

        const width = this.timeToX(end) - this.timeToX(start);
        const height = this.pHeight;
        selectionRect.lineStyle(2, this.pRangeSelectedColor, 1);

        selectionRect.beginFill(this.pRangeSelectedColor, 0.4);
        selectionRect.drawRoundedRect(0, 25, width, height - 25, 1);
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
    set startTime(time) {
        this.pStartTime = time;
        this.scaleSegment();
    }
    get startTime() {
        return this.pStartTime;
    }
    set endTime(time) {
        this.pEndTime = time;
        this.scaleSegment();
    }
    get endTime() {
        return this.pEndTime;
    }
    set time(time) {
        this.pTime = time;
        this.scaleSegment();
    }
    get time() {
        return this.pTime;
    }
    set height(height) {
        if (height !== this.pHeight) {
            this.pHeight = height;
            if (this.pBar !== null) {
                this.pBar.destroy();
                this.pBar = null;

                const bar = this.renderBar()

                const timeX = this.timeToX(this.time);
                bar.x = timeX;
                bar.y = 25;
                this.pBar = bar
                this.addChild(bar);
            }
        }

    }
    get height() {
        return this.pHeight;
    }
    set selectedRangeStart(time) {
        if (this.pSelectedRangeStart !== time) {
            this.pSelectedRangeStart = time;
            this.selectRange(this.pSelectedRangeStart, this.pSelectedRangeEnd)
        }
    }
    get selectedRangeStart() {
        return this.pSelectedRangeStart;
    }
    set selectedRangeEnd(time) {
        if (this.pSelectedRangeEnd !== time) {
            this.pSelectedRangeEnd = time;
            this.selectRange(this.pSelectedRangeStart, this.pSelectedRangeEnd)
        }
    }
    get selectedRangeEnd() {
        return this.pSelectedRangeEnd;
    }
}