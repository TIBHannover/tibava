import * as PIXI from "pixi.js";

import { Timeline } from "./timeline";

import { hex2luminance } from "./utils";


export class AnnotationTimeline extends Timeline {
  constructor({
    timelineId,
    width,
    height,
    startTime = 0,
    gap = 2,
    endTime = 10,
    duration = 10,
    data = null,
    fill = 0xffffff,
    renderer = null,
    resolution = 8192,
    segmentSelection = null,
    redrawScale = 4,
  }) {
    super({ timelineId, width, height, startTime, endTime, duration, fill });

    this.pGap = gap;
    this.pSelectedColor = 0xd99090;
    this.pTimeline = data;
    this.pSegments = {}
    this.pTimeline.segments.forEach((s) => {
      this.pSegments[s.id] = s
    })


    this.pResolution = resolution;
    this.pRenderer = renderer;

    if (segmentSelection) {
      this.pSegmentSelection = segmentSelection;
    }
    else {
      this.pSegmentSelection = [];
    }

    this.pRedrawScale = redrawScale;

    this.pRenderedStart = 0;
    this.pRenderedEnd = this.pDuration;

    this.cSegments = this.renderSegments(this.pRenderedStart, this.pRenderedEnd);
    this.addChild(this.cSegments);

    this.cAnnotations = this.renderSegmentsAnnotations(this.pRenderedStart, this.pRenderedEnd);
    this.addChild(this.cAnnotations);

    this.pTextsObjects = []
    this.pTextsContainer = new PIXI.Container();
    this.drawSegmentsAnnotationsTexts();
    this.addChild(this.pTextsContainer);

    this.cSelection = []


    const { selectionRects, selectionRectList } = this.drawSelections()
    this.cSelectionRects = selectionRects
    this.pSelectionRectList = selectionRectList
    this.addChild(selectionRects)

    this.scaleContainer();
    // this.pRect = null;
    // this._drawBox();

    // this.pBars_graphics = null;
    // this._drawBars();
  }

  drawSegmentsAnnotationsTexts() {
    // let textContainer = new PIXI.Graphics();
    // let text
    if (this.pTimeline.segments) {
      this.pTimeline.segments.forEach((s) => {

        // check if we have to render something here
        const annotationLength = s.annotations.length;
        if (annotationLength <= 0) {
          return
        }

        if (s.end < this.pStartTime || s.start > this.pEndTime) {
          return;
        }

        // check if the segment becomes to small
        const width = this.timeToX(s.end) - this.timeToX(s.start);

        // delete small annotations if exists
        if (width < 20) {
          return;
        }
        //new annotation

        const height = this.pHeight;
        const blockHeight = Math.min(height / 2, height / s.annotations.length);
        s.annotations.forEach((a, j) => {
          if (!(a.id in this.pTextsObjects)) {
            // console.log("draw text" + a.annotation.name)
            // console.log(a)

            let text = null;
            const colorHex = PIXI.utils.string2hex(a.annotation.color);
            // console.log(a.annotation.color)
            // console.log(hex2luminance(colorHex))

            const textColor = hex2luminance(colorHex) > 0.5 ? 0x000000 : 0xffffff;

            text = new PIXI.Text(a.annotation.name, {
              fill: textColor,
              fontSize: 48,
              // fontWeight: 'bold',
            });
            // if (hex2luminance(colorHex) < 0.5) {
            //   // console.log("white")
            //   text = new PIXI.Text(a.annotation.name, {
            //     fontSize: 35
            //   });
            // }
            // else {
            //   // console.log("dark")
            //   text = new PIXI.Text(a.annotation.name, { fontSize: 35 });
            // }

            const scale = (blockHeight - 2 * this.pGap) / text.height
            text.scale.set(scale, scale);
            // text.x = this.timeToX(s.start) + 2
            // text.y = j * blockHeight + this.pGap

            let rect = new PIXI.Graphics();
            rect.drawRoundedRect(0, 0, width - 4, this.pHeight - 4, 1);

            let mask = new PIXI.Graphics();
            mask.beginFill(0xffffff);
            mask.drawRoundedRect(0, 0, width - 4, this.pHeight - 4, 1);
            rect.mask = mask;
            rect.addChild(mask);
            rect.addChild(text)
            // rect.drawRoundedRect(0, 0, width, this.pHeight, 5);
            rect.x = this.timeToX(s.start) + 2
            rect.y = j * blockHeight + this.pGap
            // text.mask = mask;
            // text.addChild(mask)

            // rect.addChild(mask);
            this.pTextsContainer.addChild(rect)
            // this.pTextsContainer.addChild(rect)
            this.pTextsObjects.push(rect)
          }
        });

      });
    }
  }

  renderSegmentsAnnotations(start, end) {
    const renderWidth = this.pResolution;
    const r = renderWidth / (end - start);


    const brt = new PIXI.BaseRenderTexture({
      width: renderWidth,
      height: this.pHeight,
      // PIXI.SCALE_MODES.NEAREST,
      scaleMode: PIXI.SCALE_MODES.LINEAR,

      resolution: 1,
    });
    const rt = new PIXI.RenderTexture(brt);

    const sprite = new PIXI.Sprite(rt);

    let segmentRects = new PIXI.Graphics();


    if (this.pTimeline.segments) {
      this.pTimeline.segments.forEach((s) => {

        const annotationLength = s.annotations.length;
        if (annotationLength <= 0) {
          return
        }

        const x = r * Math.max(s.start, start);
        const width = r * (Math.min(s.end, end) - Math.max(s.start, start));
        if (width < 0.1) {
          return;
        }
        const height = this.pHeight;
        const blockHeight = height / annotationLength;
        s.annotations.forEach((a, j) => {
          // if (width < 50) {

          const color = PIXI.utils.string2hex(a.annotation.color)

          segmentRects.beginFill(color);
          segmentRects.drawRect(x, j * blockHeight + this.pGap / 2, width, blockHeight - this.pGap)
          // }
        });
      });
    }



    this.pRenderer.render(segmentRects, rt);
    return sprite;
  }

  renderSegments(start, end) {
    const renderWidth = this.pResolution;
    const r = renderWidth / (end - start);

    const colorOdd = 0xeeeeee;
    const colorEven = 0xdddddd;

    const brt = new PIXI.BaseRenderTexture({
      width: renderWidth,
      height: this.pHeight,
      // PIXI.SCALE_MODES.NEAREST,
      scaleMode: PIXI.SCALE_MODES.LINEAR,

      resolution: 1,
    });
    const rt = new PIXI.RenderTexture(brt);

    const sprite = new PIXI.Sprite(rt);

    let segmentRects = new PIXI.Graphics();


    if (this.pTimeline.segments) {
      this.pTimeline.segments.forEach((s, i) => {

        const x = r * Math.max(s.start, start) - start;
        const width = r * (Math.min(s.end, end) - Math.max(s.start, start));
        if (width < 0.1) {
          return;
        }
        const height = this.pHeight;
        segmentRects.beginFill(i % 2 == 0 ? colorOdd : colorEven);
        segmentRects.drawRect(x, 0, width, height)
      });
    }



    this.pRenderer.render(segmentRects, rt);
    return sprite;
  }

  drawSelections() {

    const selectionRects = new PIXI.Graphics();
    const selectionRectList = []
    this.pSegmentSelection.filter((segmentId) => segmentId in this.pSegments).map((segmentId) => this.pSegments[segmentId]).forEach((s) => {

      const selectionRect = new PIXI.Graphics();


      const x = this.timeToX(s.start);
      // const y = this.pY;
      const width = this.timeToX(s.end) - this.timeToX(s.start);
      const height = this.pHeight;
      selectionRect.lineStyle(2, this.pSelectedColor, 1);
      selectionRect.drawRoundedRect(0, 0, width, height, 1);
      selectionRect.x = x
      selectionRects.addChild(selectionRect)
      selectionRectList.push({ segment: s, object: selectionRect })
    })
    return { selectionRects, selectionRectList };
  }

  scaleContainer() {
    if (this.cSegments) {
      this.pTextsObjects.forEach((e) =>
        e.destroy()
      )
      this.pTextsObjects = []
      this.drawSegmentsAnnotationsTexts()
      // if (scale > this.pRedrawScale || this.pEndTime > this.pRenderedEnd || this.pStartTime < this.pRenderedStart) {
      //   this.pRenderedStart = this.pStartTime;
      //   this.pRenderedEnd = this.pEndTime;

      //   this.cSegments.destroy()
      //   this.cSegments = this.renderSegments(this.pRenderedStart, this.pRenderedEnd);
      //   this.addChild(this.cSegments);

      //   this.cAnnotations.destroy()
      //   this.cAnnotations = this.renderSegmentsAnnotations(this.pRenderedStart, this.pRenderedEnd);

      //   this.addChild(this.cAnnotations);
      // }
      // if ((this.pRenderedEnd - this.pRenderedStart))
      const width = this.timeToX(this.pRenderedEnd) - this.timeToX(this.pRenderedStart);
      const x = this.timeToX(this.pRenderedStart);
      this.cSegments.x = x;
      this.cSegments.width = width;
      this.cAnnotations.x = x;
      this.cAnnotations.width = width;

      this.pSelectionRectList.forEach((s) => {
        s.object.x = this.timeToX(s.segment.start)
        s.object.width = this.timeToX(s.segment.end) - this.timeToX(s.segment.start)
      })
    }
  }

  clearSegmentSelection() {
    this.pSegmentSelection = []
  }
  addSegmentSelection(segmentId) {
    this.pSegmentSelection.push(segmentId)
    const { selectionRects, selectionRectList } = this.drawSelections()
    this.cSelectionRects.destroy();
    this.cSelectionRects = selectionRects
    this.pSelectionRectList = selectionRectList
    this.addChild(selectionRects)
  }
  removeSegmentSelection(segmentId) {
    let index = this.pSegmentSelection.findIndex(
      (f) => f === segmentId
    );
    this.pSegmentSelection.splice(index, 1);
    const { selectionRects, selectionRectList } = this.drawSelections()
    this.cSelectionRects.destroy();
    this.cSelectionRects = selectionRects
    this.pSelectionRectList = selectionRectList
    this.addChild(selectionRects)
  }
  getSegmentOnPosition(xPos) {
    const time = this.xToTime(xPos)
    let result = null;
    this.pTimeline.segments.forEach((s, i) => {
      if (time > s.start && time < s.end) {
        result = {segment: s, index: i};
      }
    });
    return result
  }
}