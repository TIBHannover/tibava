
export class TimelineHeader extends PIXI.Container {
    constructor(timeline, x, y, width, height, fill = 0xffffff) {
        super();
        this.pTimeline = timeline;
        this.pX = x;
        this.pY = y;
        this.pWidth = width;
        this.pHeight = height;

        const padding = 2;
        const gap = 4;

        this.pRect = new PIXI.Graphics();
        this.pRect.beginFill(fill);
        this.pRect.drawRoundedRect(0, 0, width, height, 5);
        this.pRect.x = x;
        this.pRect.y = y;

        this.pMask = new PIXI.Graphics();
        this.pMask.beginFill(0xffffff);
        this.pMask.drawRoundedRect(0, 0, width, height, 5);
        this.pRect.mask = this.pMask;
        this.pRect.addChild(this.pMask);

        let shadow = new DropShadowFilter();
        shadow.color = 0x0000;
        shadow.distance = 2;
        shadow.alpha = 0.4;
        shadow.rotation = 90;
        shadow.blur = 1;
        this.pRect.filters = [shadow];

        this.addChild(this.pRect);
        this.pText = new PIXI.Text(timeline.name, {
            fill: 0x000000,
            fontSize: 16,
            // fontWeight: 'bold',
        });
        this.pText.x = gap;
        this.pText.y = gap;
        this.pText.mask = this.pMask;

        this.pRect.addChild(this.pText);

        this.interactive = true;
        this.buttonMode = true;
        this.on("rightdown", (ev) => {
            this.emit("timelineRightDown", {
                event: ev,
                timeline: this,
            });
            ev.stopPropagation();
        });

        this.on("click", (ev) => {
            this.emit("timelineClick", {
                event: ev,
                timeline: this,
            });
            ev.stopPropagation();
        });
    }

    set width(value) {
        this.pRect.width = value;
    }
    get timeline() {
        return this.pTimeline;
    }
}
