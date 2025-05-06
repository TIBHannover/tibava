import * as PIXI from "pixi.js";
import { DropShadowFilter, TiltShiftAxisFilter } from "pixi-filters";

export class Button extends PIXI.Container {
    constructor(x, y, width, height, icon) {
        super();
        this.pX = x;
        this.pY = y;
        this.pMargin = 2;
        this.pWidth = width;
        this.pHeight = height;
        this.pSprite = PIXI.Sprite.from(icon);
        this.pSprite.x = this.pMargin;
        this.pSprite.y = this.pMargin;

        this.pBoxWidth = this.pSprite.width + 2 * this.pMargin;
        this.pBoxHeight = this.pSprite.height + 2 * this.pMargin;

        this.pRect = new PIXI.Graphics();
        this.pRect.beginFill(0xffffff);
        this.pRect.drawRoundedRect(0, 0, this.pBoxWidth, this.pBoxHeight, 5);
        this.pRect.x = x;
        this.pRect.y = y;

        this.pRect.addChild(this.pSprite);
        // this.pMask = new PIXI.Graphics();
        // this.pMask.beginFill(0xffffff);
        // this.pMask.drawRoundedRect(0, 0, this.pBoxWidth, this.pBoxHeight, 5);

        // this.pRect.mask = this.pMask;

        let shadow = new DropShadowFilter();
        shadow.color = 0x0000;
        shadow.distance = 2;
        shadow.alpha = 0.4;
        shadow.rotation = 90;
        shadow.blur = 1;
        this.pRect.filters = [shadow];

        this.addChild(this.pRect);
        this.pRect.interactive = true;
        this.pRect.buttonMode = true;
        this.pRect.on("pointerover", this.onButtonOver);
        this.pRect.on("pointerout", this.onButtonOut);

        this.pRect.on("pointerdown", this.onButtonDown);
        this.pRect.on("pointerup", this.onButtonUp);
        this.pRect.on("pointerupoutside", this.onButtonUp);
        this.pRect.on("click", this.onClick);
    }
    onButtonOver = () => {
        this.pIsOver = true;
        if (this.pIsDown) {
            return;
        }
        this.pRect.clear();
        this.pRect.beginFill(0xeeeeee);
        this.pRect.drawRoundedRect(0, 0, this.pBoxWidth, this.pBoxHeight, 5);
    };
    onButtonOut = () => {
        this.pIsOver = false;
        if (this.pIsDown) {
            return;
        }
        this.pRect.clear();
        this.pRect.beginFill(0xffffff);
        this.pRect.drawRoundedRect(0, 0, this.pBoxWidth, this.pBoxHeight, 5);
    };
    onButtonUp = () => {
        this.pIsDown = false;

        let shadow = new DropShadowFilter();
        shadow.color = 0x0000;
        shadow.distance = 2;
        shadow.alpha = 0.4;
        shadow.rotation = 90;
        shadow.blur = 1;
        this.pRect.filters = [shadow];
    };
    onButtonDown = (event) => {
        this.pIsDown = true;

        let shadow = new DropShadowFilter();
        shadow.color = 0x0000;
        shadow.distance = 0;
        shadow.alpha = 0.4;
        shadow.rotation = 90;
        shadow.blur = 1;
        this.pRect.filters = [shadow];
    };
    onClick = (event) => {
        this.emit("click", event);
    };
}
