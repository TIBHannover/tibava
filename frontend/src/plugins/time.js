export function get_display_time(seconds) {
    var h = Math.floor(seconds / 3600);
    var m = Math.floor((seconds % 3600) / 60);
    var s = Math.floor((seconds % 3600) % 60);

    var hDisplay = h > 0 ? h + (h == 1 ? " h " : " h ") : "";
    var mDisplay = m > 0 ? m + (m == 1 ? " min " : " min ") : "";
    var sDisplay = s > 0 ? s + (s == 1 ? " sec" : " sec") : "";
    return hDisplay + mDisplay + sDisplay;
}

export function get_timecode(seconds, num_digits_ms = 3) {

    var h = Math.floor(seconds / 3600);
    var m = Math.floor((seconds % 3600) / 60);
    // var s = Math.round((seconds % 3600) % 60);
    var s = Math.floor((seconds % 3600) % 60);
    var ms = Math.round(10 ** num_digits_ms * (((seconds % 3600) % 60) % 1))

    const zeroPad = (num, places) => String(num).padStart(places, '0')
    if (num_digits_ms > 0){
        return zeroPad(h, 2) + ":" + zeroPad(m, 2) + ":" + zeroPad(s, 2) + "." + zeroPad(ms, num_digits_ms);
    }else{
        return zeroPad(h, 2) + ":" + zeroPad(m, 2) + ":" + zeroPad(s, 2);
    }
}
