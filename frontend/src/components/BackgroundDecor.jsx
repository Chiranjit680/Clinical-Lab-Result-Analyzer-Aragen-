/**
 * Decorative background: a DNA double helix, molecule rings and an instrument
 * trace, behind everything and announced to nobody.
 *
 * Inline SVG rather than image assets so the shapes inherit the palette tokens
 * and cost nothing to download. The geometry is generated, not hand-drawn: the
 * helix is two phase-shifted sine strands whose rungs fade as they turn
 * edge-on, which is what makes a flat drawing read as a twist.
 *
 * Every element here is aria-hidden and pointer-events: none — it must never
 * take focus, intercept a click, or be read aloud.
 */
export default function BackgroundDecor() {
  return (
    <div className="decor" aria-hidden="true">
      <svg
        className="decor__helix"
        viewBox="0 0 200 900"
        preserveAspectRatio="xMidYMin slice"
        fill="none"
        stroke="var(--blue-500)"
        strokeWidth="2.4"
        strokeLinecap="round"
      >
        <polyline points="100.0,0 109.5,6 118.7,12 127.4,18 135.4,24 142.4,30 148.3,36 152.9,42 156.1,48 157.7,54 157.9,60 156.4,66 153.5,72 149.1,78 143.5,84 136.6,90 128.8,96 120.2,102 111.0,108 101.6,114 92.1,120 82.8,126 74.0,132 65.9,138 58.7,144 52.6,150 47.8,156 44.4,162 42.4,168 42.0,174 43.2,180 45.9,186 50.0,192 55.5,198 62.2,204 69.9,210 78.4,216 87.4,222 96.8,228 106.3,234 115.6,240 124.6,246 132.8,252 140.2,258 146.5,264 151.5,270 155.2,276 157.3,282 158.0,288 157.1,294 154.7,300 150.7,306 145.5,312 139.0,318 131.5,324 123.1,330 114.1,336 104.7,342 95.3,348 85.9,354 76.9,360 68.5,366 61.0,372 54.5,378 49.3,384 45.3,390 42.9,396 42.0,402 42.7,408 44.8,414 48.5,420 53.5,426 59.8,432 67.2,438 75.4,444 84.4,450 93.7,456 103.2,462 112.6,468 121.6,474 130.1,480 137.8,486 144.5,492 150.0,498 154.1,504 156.8,510 158.0,516 157.6,522 155.6,528 152.2,534 147.4,540 141.3,546 134.1,552 126.0,558 117.2,564 107.9,570 98.4,576 89.0,582 79.8,588 71.2,594 63.4,600 56.5,606 50.9,612 46.5,618 43.6,624 42.1,630 42.3,636 43.9,642 47.1,648 51.7,654 57.6,660 64.6,666 72.6,672 81.3,678 90.5,684 100.0,690 109.5,696 118.7,702 127.4,708 135.4,714 142.4,720 148.3,726 152.9,732 156.1,738 157.7,744 157.9,750 156.4,756 153.5,762 149.1,768 143.5,774 136.6,780 128.8,786 120.2,792 111.0,798 101.6,804 92.1,810 82.8,816 74.0,822 65.9,828 58.7,834 52.6,840 47.8,846 44.4,852 42.4,858 42.0,864 43.2,870 45.9,876 50.0,882 55.5,888 62.2,894 69.9,900" strokeOpacity="0.5" />
        <polyline points="100.0,0 90.5,6 81.3,12 72.6,18 64.6,24 57.6,30 51.7,36 47.1,42 43.9,48 42.3,54 42.1,60 43.6,66 46.5,72 50.9,78 56.5,84 63.4,90 71.2,96 79.8,102 89.0,108 98.4,114 107.9,120 117.2,126 126.0,132 134.1,138 141.3,144 147.4,150 152.2,156 155.6,162 157.6,168 158.0,174 156.8,180 154.1,186 150.0,192 144.5,198 137.8,204 130.1,210 121.6,216 112.6,222 103.2,228 93.7,234 84.4,240 75.4,246 67.2,252 59.8,258 53.5,264 48.5,270 44.8,276 42.7,282 42.0,288 42.9,294 45.3,300 49.3,306 54.5,312 61.0,318 68.5,324 76.9,330 85.9,336 95.3,342 104.7,348 114.1,354 123.1,360 131.5,366 139.0,372 145.5,378 150.7,384 154.7,390 157.1,396 158.0,402 157.3,408 155.2,414 151.5,420 146.5,426 140.2,432 132.8,438 124.6,444 115.6,450 106.3,456 96.8,462 87.4,468 78.4,474 69.9,480 62.2,486 55.5,492 50.0,498 45.9,504 43.2,510 42.0,516 42.4,522 44.4,528 47.8,534 52.6,540 58.7,546 65.9,552 74.0,558 82.8,564 92.1,570 101.6,576 111.0,582 120.2,588 128.8,594 136.6,600 143.5,606 149.1,612 153.5,618 156.4,624 157.9,630 157.7,636 156.1,642 152.9,648 148.3,654 142.4,660 135.4,666 127.4,672 118.7,678 109.5,684 100.0,690 90.5,696 81.3,702 72.6,708 64.6,714 57.6,720 51.7,726 47.1,732 43.9,738 42.3,744 42.1,750 43.6,756 46.5,762 50.9,768 56.5,774 63.4,780 71.2,786 79.8,792 89.0,798 98.4,804 107.9,810 117.2,816 126.0,822 134.1,828 141.3,834 147.4,840 152.2,846 155.6,852 157.6,858 158.0,864 156.8,870 154.1,876 150.0,882 144.5,888 137.8,894 130.1,900" strokeOpacity="0.32" />
        <g strokeWidth="1.8">
        <line x1="117.2" y1="11" x2="82.8" y2="11" strokeOpacity="0.41" />
        <circle cx="117.2" cy="11" r="3.0" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <circle cx="82.8" cy="11" r="3.0" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <line x1="146.5" y1="34" x2="53.5" y2="34" strokeOpacity="0.69" />
        <circle cx="146.5" cy="34" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <circle cx="53.5" cy="34" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <line x1="158.0" y1="57" x2="42.0" y2="57" strokeOpacity="0.80" />
        <circle cx="158.0" cy="57" r="4.1" fill="var(--blue-500)" fillOpacity="0.32" stroke="none" />
        <circle cx="42.0" cy="57" r="4.1" fill="var(--blue-500)" fillOpacity="0.32" stroke="none" />
        <line x1="147.4" y1="80" x2="52.6" y2="80" strokeOpacity="0.70" />
        <circle cx="147.4" cy="80" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <circle cx="52.6" cy="80" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <line x1="118.7" y1="103" x2="81.3" y2="103" strokeOpacity="0.43" />
        <circle cx="118.7" cy="103" r="3.1" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <circle cx="81.3" cy="103" r="3.1" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <line x1="82.8" y1="126" x2="117.2" y2="126" strokeOpacity="0.41" />
        <circle cx="82.8" cy="126" r="3.0" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <circle cx="117.2" cy="126" r="3.0" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <line x1="53.5" y1="149" x2="146.5" y2="149" strokeOpacity="0.69" />
        <circle cx="53.5" cy="149" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <circle cx="146.5" cy="149" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <line x1="42.0" y1="172" x2="158.0" y2="172" strokeOpacity="0.80" />
        <circle cx="42.0" cy="172" r="4.1" fill="var(--blue-500)" fillOpacity="0.32" stroke="none" />
        <circle cx="158.0" cy="172" r="4.1" fill="var(--blue-500)" fillOpacity="0.32" stroke="none" />
        <line x1="52.6" y1="195" x2="147.4" y2="195" strokeOpacity="0.70" />
        <circle cx="52.6" cy="195" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <circle cx="147.4" cy="195" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <line x1="81.3" y1="218" x2="118.7" y2="218" strokeOpacity="0.43" />
        <circle cx="81.3" cy="218" r="3.1" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <circle cx="118.7" cy="218" r="3.1" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <line x1="117.2" y1="241" x2="82.8" y2="241" strokeOpacity="0.41" />
        <circle cx="117.2" cy="241" r="3.0" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <circle cx="82.8" cy="241" r="3.0" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <line x1="146.5" y1="264" x2="53.5" y2="264" strokeOpacity="0.69" />
        <circle cx="146.5" cy="264" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <circle cx="53.5" cy="264" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <line x1="158.0" y1="287" x2="42.0" y2="287" strokeOpacity="0.80" />
        <circle cx="158.0" cy="287" r="4.1" fill="var(--blue-500)" fillOpacity="0.32" stroke="none" />
        <circle cx="42.0" cy="287" r="4.1" fill="var(--blue-500)" fillOpacity="0.32" stroke="none" />
        <line x1="147.4" y1="310" x2="52.6" y2="310" strokeOpacity="0.70" />
        <circle cx="147.4" cy="310" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <circle cx="52.6" cy="310" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <line x1="118.7" y1="333" x2="81.3" y2="333" strokeOpacity="0.43" />
        <circle cx="118.7" cy="333" r="3.1" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <circle cx="81.3" cy="333" r="3.1" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <line x1="82.8" y1="356" x2="117.2" y2="356" strokeOpacity="0.41" />
        <circle cx="82.8" cy="356" r="3.0" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <circle cx="117.2" cy="356" r="3.0" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <line x1="53.5" y1="379" x2="146.5" y2="379" strokeOpacity="0.69" />
        <circle cx="53.5" cy="379" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <circle cx="146.5" cy="379" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <line x1="42.0" y1="402" x2="158.0" y2="402" strokeOpacity="0.80" />
        <circle cx="42.0" cy="402" r="4.1" fill="var(--blue-500)" fillOpacity="0.32" stroke="none" />
        <circle cx="158.0" cy="402" r="4.1" fill="var(--blue-500)" fillOpacity="0.32" stroke="none" />
        <line x1="52.6" y1="425" x2="147.4" y2="425" strokeOpacity="0.70" />
        <circle cx="52.6" cy="425" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <circle cx="147.4" cy="425" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <line x1="81.3" y1="448" x2="118.7" y2="448" strokeOpacity="0.43" />
        <circle cx="81.3" cy="448" r="3.1" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <circle cx="118.7" cy="448" r="3.1" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <line x1="117.2" y1="471" x2="82.8" y2="471" strokeOpacity="0.41" />
        <circle cx="117.2" cy="471" r="3.0" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <circle cx="82.8" cy="471" r="3.0" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <line x1="146.5" y1="494" x2="53.5" y2="494" strokeOpacity="0.69" />
        <circle cx="146.5" cy="494" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <circle cx="53.5" cy="494" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <line x1="158.0" y1="517" x2="42.0" y2="517" strokeOpacity="0.80" />
        <circle cx="158.0" cy="517" r="4.1" fill="var(--blue-500)" fillOpacity="0.32" stroke="none" />
        <circle cx="42.0" cy="517" r="4.1" fill="var(--blue-500)" fillOpacity="0.32" stroke="none" />
        <line x1="147.4" y1="540" x2="52.6" y2="540" strokeOpacity="0.70" />
        <circle cx="147.4" cy="540" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <circle cx="52.6" cy="540" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <line x1="118.7" y1="563" x2="81.3" y2="563" strokeOpacity="0.43" />
        <circle cx="118.7" cy="563" r="3.1" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <circle cx="81.3" cy="563" r="3.1" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <line x1="82.8" y1="586" x2="117.2" y2="586" strokeOpacity="0.41" />
        <circle cx="82.8" cy="586" r="3.0" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <circle cx="117.2" cy="586" r="3.0" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <line x1="53.5" y1="609" x2="146.5" y2="609" strokeOpacity="0.69" />
        <circle cx="53.5" cy="609" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <circle cx="146.5" cy="609" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <line x1="42.0" y1="632" x2="158.0" y2="632" strokeOpacity="0.80" />
        <circle cx="42.0" cy="632" r="4.1" fill="var(--blue-500)" fillOpacity="0.32" stroke="none" />
        <circle cx="158.0" cy="632" r="4.1" fill="var(--blue-500)" fillOpacity="0.32" stroke="none" />
        <line x1="52.6" y1="655" x2="147.4" y2="655" strokeOpacity="0.70" />
        <circle cx="52.6" cy="655" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <circle cx="147.4" cy="655" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <line x1="81.3" y1="678" x2="118.7" y2="678" strokeOpacity="0.43" />
        <circle cx="81.3" cy="678" r="3.1" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <circle cx="118.7" cy="678" r="3.1" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <line x1="117.2" y1="701" x2="82.8" y2="701" strokeOpacity="0.41" />
        <circle cx="117.2" cy="701" r="3.0" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <circle cx="82.8" cy="701" r="3.0" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <line x1="146.5" y1="724" x2="53.5" y2="724" strokeOpacity="0.69" />
        <circle cx="146.5" cy="724" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <circle cx="53.5" cy="724" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <line x1="158.0" y1="747" x2="42.0" y2="747" strokeOpacity="0.80" />
        <circle cx="158.0" cy="747" r="4.1" fill="var(--blue-500)" fillOpacity="0.32" stroke="none" />
        <circle cx="42.0" cy="747" r="4.1" fill="var(--blue-500)" fillOpacity="0.32" stroke="none" />
        <line x1="147.4" y1="770" x2="52.6" y2="770" strokeOpacity="0.70" />
        <circle cx="147.4" cy="770" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <circle cx="52.6" cy="770" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <line x1="118.7" y1="793" x2="81.3" y2="793" strokeOpacity="0.43" />
        <circle cx="118.7" cy="793" r="3.1" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <circle cx="81.3" cy="793" r="3.1" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <line x1="82.8" y1="816" x2="117.2" y2="816" strokeOpacity="0.41" />
        <circle cx="82.8" cy="816" r="3.0" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <circle cx="117.2" cy="816" r="3.0" fill="var(--blue-500)" fillOpacity="0.17" stroke="none" />
        <line x1="53.5" y1="839" x2="146.5" y2="839" strokeOpacity="0.69" />
        <circle cx="53.5" cy="839" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <circle cx="146.5" cy="839" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <line x1="42.0" y1="862" x2="158.0" y2="862" strokeOpacity="0.80" />
        <circle cx="42.0" cy="862" r="4.1" fill="var(--blue-500)" fillOpacity="0.32" stroke="none" />
        <circle cx="158.0" cy="862" r="4.1" fill="var(--blue-500)" fillOpacity="0.32" stroke="none" />
        <line x1="52.6" y1="885" x2="147.4" y2="885" strokeOpacity="0.70" />
        <circle cx="52.6" cy="885" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        <circle cx="147.4" cy="885" r="3.8" fill="var(--blue-500)" fillOpacity="0.28" stroke="none" />
        </g>
      </svg>

      <svg
        className="decor__molecule decor__molecule--top"
        viewBox="0 0 180 140"
        fill="none"
        stroke="var(--blue-500)"
        strokeWidth="2.2"
        strokeOpacity="0.42"
        strokeLinejoin="round"
      >
        <polygon points="89.4,87.0 60.0,104.0 30.6,87.0 30.6,53.0 60.0,36.0 89.4,53.0" />
        <polygon points="148.3,87.0 118.9,104.0 89.4,87.0 89.4,53.0 118.9,36.0 148.3,53.0" />
        <line x1="30.6" y1="87.0" x2="16.7" y2="95.0" />
        <circle cx="16.7" cy="95.0" r="3.4" fill="var(--blue-500)" fillOpacity="0.18" stroke="none" />
        <line x1="30.6" y1="53.0" x2="16.7" y2="45.0" />
        <circle cx="16.7" cy="45.0" r="3.4" fill="var(--blue-500)" fillOpacity="0.18" stroke="none" />
        <line x1="148.3" y1="53.0" x2="162.2" y2="45.0" />
        <circle cx="162.2" cy="45.0" r="3.4" fill="var(--blue-500)" fillOpacity="0.18" stroke="none" />
        <line x1="148.3" y1="87.0" x2="162.2" y2="95.0" />
        <circle cx="162.2" cy="95.0" r="3.4" fill="var(--blue-500)" fillOpacity="0.18" stroke="none" />
      </svg>

      <svg
        className="decor__molecule decor__molecule--bottom"
        viewBox="0 0 120 120"
        fill="none"
        stroke="var(--orange-500)"
        strokeWidth="2.2"
        strokeOpacity="0.38"
        strokeLinejoin="round"
      >
        <polygon points="81.0,70.0 55.0,85.0 29.0,70.0 29.0,40.0 55.0,25.0 81.0,40.0" />
        <line x1="55.0" y1="85.0" x2="55.0" y2="103.0" />
        <circle cx="55.0" cy="103.0" r="3.2" fill="var(--orange-500)" fillOpacity="0.16" stroke="none" />
        <line x1="55.0" y1="25.0" x2="55.0" y2="7.0" />
        <circle cx="55.0" cy="7.0" r="3.2" fill="var(--orange-500)" fillOpacity="0.16" stroke="none" />
      </svg>

      <svg
        className="decor__trace"
        viewBox="0 0 1200 80"
        preserveAspectRatio="none"
        fill="none"
        stroke="var(--blue-500)"
        strokeWidth="2"
        strokeOpacity="0.3"
        strokeLinecap="round"
      >
        <polyline points="0,40.0 4,40.5 8,40.9 12,41.2 16,41.2 20,41.0 24,40.5 28,40.0 32,39.5 36,39.1 40,40.0 44,37.4 48,34.0 52,29.4 56,23.7 60,17.3 64,11.3 68,6.9 72,5.2 76,7.1 80,12.9 84,22.1 88,33.8 92,39.1 96,38.9 100,38.8 104,39.0 108,39.4 112,39.9 116,40.4 120,40.8 124,41.1 128,41.2 132,41.0 136,40.7 140,40.2 144,39.7 148,39.2 152,38.9 156,38.8 160,38.9 164,39.3 168,39.8 172,40.3 176,40.8 180,41.1 184,41.2 188,41.1 192,40.7 196,40.3 200,39.7 204,39.2 208,38.9 212,38.8 216,38.9 220,39.2 224,39.7 228,40.2 232,40.7 236,41.1 240,41.2 244,41.1 248,40.8 252,40.3 256,39.8 260,39.3 264,39.0 268,38.8 272,38.9 276,39.2 280,39.6 284,40.2 288,40.7 292,41.0 296,41.2 300,41.1 304,40.8 308,40.4 312,39.9 316,39.4 320,39.0 324,38.8 328,38.9 332,39.1 336,39.6 340,40.0 344,37.4 348,34.0 352,29.4 356,23.7 360,17.3 364,11.3 368,6.9 372,5.2 376,7.1 380,12.9 384,22.1 388,33.8 392,39.5 396,40.0 400,40.5 404,40.9 408,41.2 412,41.2 416,40.9 420,40.5 424,40.0 428,39.5 432,39.1 436,38.8 440,38.8 444,39.0 448,39.4 452,39.9 456,40.5 460,40.9 464,41.2 468,41.2 472,41.0 476,40.6 480,40.1 484,39.6 488,39.1 492,38.9 496,38.8 500,39.0 504,39.4 508,39.9 512,40.4 516,40.8 520,41.1 524,41.2 528,41.0 532,40.7 536,40.2 540,39.6 544,39.2 548,38.9 552,38.8 556,39.0 560,39.3 564,39.8 568,40.3 572,40.8 576,41.1 580,41.2 584,41.1 588,40.7 592,40.2 596,39.7 600,39.2 604,38.9 608,38.8 612,38.9 616,39.3 620,39.7 624,40.3 628,40.7 632,41.1 636,41.2 640,40.0 644,37.4 648,34.0 652,29.4 656,23.7 660,17.3 664,11.3 668,6.9 672,5.2 676,7.1 680,12.9 684,22.1 688,33.8 692,41.2 696,41.1 700,40.8 704,40.4 708,39.8 712,39.4 716,39.0 720,38.8 724,38.9 728,39.1 732,39.6 736,40.1 740,40.6 744,41.0 748,41.2 752,41.1 756,40.9 760,40.4 764,39.9 768,39.4 772,39.0 776,38.8 780,38.8 784,39.1 788,39.5 792,40.0 796,40.6 800,41.0 804,41.2 808,41.2 812,40.9 816,40.5 820,40.0 824,39.5 828,39.1 832,38.8 836,38.8 840,39.0 844,39.5 848,40.0 852,40.5 856,40.9 860,41.2 864,41.2 868,41.0 872,40.6 876,40.1 880,39.5 884,39.1 888,38.9 892,38.8 896,39.0 900,39.4 904,39.9 908,40.4 912,40.9 916,41.1 920,41.2 924,41.0 928,40.6 932,40.1 936,39.6 940,40.0 944,37.4 948,34.0 952,29.4 956,23.7 960,17.3 964,11.3 968,6.9 972,5.2 976,7.1 980,12.9 984,22.1 988,33.8 992,39.7 996,39.2 1000,38.9 1004,38.8 1008,38.9 1012,39.3 1016,39.8 1020,40.3 1024,40.8 1028,41.1 1032,41.2 1036,41.1 1040,40.8 1044,40.3 1048,39.8 1052,39.3 1056,38.9 1060,38.8 1064,38.9 1068,39.2 1072,39.7 1076,40.2 1080,40.7 1084,41.0 1088,41.2 1092,41.1 1096,40.8 1100,40.4 1104,39.8 1108,39.3 1112,39.0 1116,38.8 1120,38.9 1124,39.2 1128,39.6 1132,40.1 1136,40.6 1140,41.0 1144,41.2 1148,41.1 1152,40.9 1156,40.4 1160,39.9 1164,39.4 1168,39.0 1172,38.8 1176,38.9 1180,39.1 1184,39.5 1188,40.1 1192,40.6 1196,41.0 1200,41.2" />
      </svg>

      {/* Culture dishes: concentric rings, nothing cleverer. */}
      <svg
        className="decor__dishes"
        viewBox="0 0 220 220"
        fill="none"
        stroke="var(--blue-500)"
        strokeOpacity="0.3"
        strokeWidth="2"
      >
        <circle cx="78" cy="78" r="56" />
        <circle cx="78" cy="78" r="40" strokeOpacity="0.2" />
        <circle cx="150" cy="140" r="44" />
        <circle cx="150" cy="140" r="30" strokeOpacity="0.2" />
        <circle cx="78" cy="78" r="7" fill="var(--blue-500)" fillOpacity="0.14" stroke="none" />
        <circle cx="150" cy="140" r="6" fill="var(--orange-500)" fillOpacity="0.16" stroke="none" />
      </svg>
    </div>
  );
}
