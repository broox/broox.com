(function () {
  'use strict';

  var GROUPS = [
    { rating: 3, title: '★★★ Wow', blurb: 'power colors, head to toe' },
    { rating: 2, title: '★★ Excellent', blurb: 'strong choices' },
    { rating: 1, title: '★ Significant', blurb: 'pops, patterns & accessories' }
  ];
  var NOTES = {
    'BW': 'Below waist',
    'BLN': 'Best light neutral',
    'BDN': 'Best deep neutral',
    'Love!': 'Love!'
  };
  var WHITE_CHECK = {
    name: 'White check',
    hex: '#FFFFFF',
    p3: '1 1 1',
    caption: 'This should look pure white. Cream or orange means Night Shift or True Tone is on.'
  };
  var TIP_KEY = 'colors-display-tip-dismissed';

  // Prefer Display P3 values on wide-gamut screens (e.g. iPhone): closer for the saturated reds.
  var useP3 = !!(window.CSS && CSS.supports && CSS.supports('color', 'color(display-p3 1 0 0)')) &&
    !!(window.matchMedia && matchMedia('(color-gamut: p3)').matches);

  function photoColor(c) {
    return useP3 ? 'color(display-p3 ' + c.p3 + ')' : c.hex;
  }

  // Black or white text, whichever has more contrast against the color.
  function inkFor(hex) {
    var n = parseInt(hex.slice(1), 16);
    var lum = [n >> 16, (n >> 8) & 255, n & 255].map(function (v) {
      v /= 255;
      return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
    });
    var L = 0.2126 * lum[0] + 0.7152 * lum[1] + 0.0722 * lum[2];
    return (L + 0.05) / 0.05 > 1.05 / (L + 0.05) ? 'rgba(0,0,0,0.82)' : 'rgba(255,255,255,0.92)';
  }

  function paintHalf(node, hex, css) {
    node.style.background = hex;
    if (css && css !== hex) node.style.background = css;
    node.style.setProperty('--ink', inkFor(hex));
  }

  function stars(n) {
    return '★★★'.slice(0, n);
  }

  function noteText(c) {
    return c.note ? (NOTES[c.note] || c.note) : '';
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  // --- Build the list: by rating, tagged colors first, then by swatch number ---
  var ordered = [];
  var root = document.getElementById('swatches');

  GROUPS.forEach(function (g) {
    var colors = window.PALETTE.filter(function (c) { return c.rating === g.rating; })
      .sort(function (a, b) { return (b.note ? 1 : 0) - (a.note ? 1 : 0) || a.n - b.n; });
    if (!colors.length) return;

    var h = el('h2', 'group-heading', g.title + ' ');
    h.appendChild(el('span', null, '· ' + g.blurb));
    root.appendChild(h);

    colors.forEach(function (c) {
      var idx = ordered.push(c) - 1;
      var b = el('button', 'swatch');
      b.type = 'button';

      // Left: photo of the swatch.
      var left = el('span', 'half photo-half');
      paintHalf(left, c.hex, photoColor(c));
      left.appendChild(el('span', 'swatch-name', c.name));
      if (c.note) left.appendChild(el('span', 'badge', noteText(c)));
      left.appendChild(el('span', 'swatch-meta', stars(c.rating) + '  ·  #' + c.n));
      left.appendChild(el('span', 'swatch-hex', 'Photo ' + c.hex + (c.estimated ? ' (est.)' : '')));
      b.appendChild(left);

      // Right: House of Colour wheel graphic.
      var right = el('span', 'half wheel-half');
      if (c.wheel) {
        paintHalf(right, c.wheel);
        right.appendChild(el('span', 'swatch-hex', 'Wheel ' + c.wheel));
      } else {
        right.classList.add('missing');
        right.appendChild(el('span', 'swatch-hex', 'Not on the wheel'));
      }
      b.appendChild(right);

      b.setAttribute('aria-label', c.name + ', ' + c.rating + ' stars' + (c.note ? ', ' + noteText(c) : '') +
        '. Photo ' + c.hex + (c.wheel ? ', wheel ' + c.wheel : ', not on the wheel'));
      b.addEventListener('click', function () { open(idx); });
      root.appendChild(b);
    });
  });

  // --- Full screen (split the same way) -----------------------------------------
  var fs = document.getElementById('fullscreen');
  var fsLeft = document.getElementById('fs-left');
  var fsRight = document.getElementById('fs-right');
  var themeMeta = document.querySelector('meta[name="theme-color"]');
  var current = null; // index into ordered, or 'white'
  var lastFocus = null;

  function setLabel(half, title, line) {
    var label = half.querySelector('.fs-label');
    label.textContent = '';
    label.appendChild(el('strong', null, title));
    label.appendChild(el('span', null, line));
  }

  function paint(c) {
    var single = c === WHITE_CHECK;
    fs.classList.toggle('single', single);
    paintHalf(fsLeft, c.hex, photoColor(c));
    // Tint the browser chrome and overscroll area to match.
    themeMeta.setAttribute('content', c.hex);
    document.documentElement.style.background = c.hex;

    if (single) {
      setLabel(fsLeft, c.name, c.caption);
      return;
    }
    var pos = (current + 1) + '/' + ordered.length;
    setLabel(fsLeft, c.name, 'Photo ' + c.hex + '  ·  ' + stars(c.rating) + (c.note ? '  ·  ' + noteText(c) : ''));
    fsRight.classList.toggle('missing', !c.wheel);
    if (c.wheel) {
      paintHalf(fsRight, c.wheel);
      setLabel(fsRight, 'Wheel', c.wheel + '  ·  ' + pos);
    } else {
      fsRight.style.background = '';
      fsRight.style.setProperty('--ink', '#777');
      fsRight.style.background = 'repeating-linear-gradient(45deg, #eee 0 10px, #f8f8f8 10px 20px)';
      setLabel(fsRight, 'Wheel', 'Not on the wheel  ·  ' + pos);
    }
  }

  function open(which) {
    var wasOpen = current !== null;
    current = which;
    paint(which === 'white' ? WHITE_CHECK : ordered[which]);
    if (!wasOpen) {
      lastFocus = document.activeElement;
      fs.hidden = false;
      document.body.classList.add('locked');
      fs.tabIndex = -1;
      fs.focus();
      // Let the phone's back gesture close the color instead of leaving the page.
      try { history.pushState({ colorsFullscreen: true }, ''); } catch (e) {}
    }
  }

  function close(fromHistory) {
    if (current === null) return;
    current = null;
    fs.hidden = true;
    document.body.classList.remove('locked');
    themeMeta.setAttribute('content', '#ffffff');
    document.documentElement.style.background = '';
    if (!fromHistory && history.state && history.state.colorsFullscreen) {
      try { history.back(); } catch (e) {}
    }
    if (lastFocus) lastFocus.focus({ preventScroll: true });
  }

  function step(delta) {
    if (current === null || current === 'white') return;
    open((current + delta + ordered.length) % ordered.length);
  }

  window.addEventListener('popstate', function () { close(true); });

  // Tap to close, swipe left/right for the next/previous color.
  var startX = 0, startY = 0, tracking = false;
  fs.addEventListener('pointerdown', function (e) {
    tracking = true; startX = e.clientX; startY = e.clientY;
  });
  fs.addEventListener('pointerup', function (e) {
    if (!tracking) return;
    tracking = false;
    var dx = e.clientX - startX, dy = e.clientY - startY;
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy)) {
      step(dx < 0 ? 1 : -1);
    } else if (Math.abs(dx) < 10 && Math.abs(dy) < 10) {
      close();
    }
  });
  fs.addEventListener('pointercancel', function () { tracking = false; });

  document.addEventListener('keydown', function (e) {
    if (current === null) return;
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') step(1);
    else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') step(-1);
    else if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); close(); }
  });

  document.getElementById('white-check').addEventListener('click', function () { open('white'); });

  // --- Display tip (Night Shift / True Tone can't be detected from a web page) ---
  var tip = document.getElementById('display-tip');
  var dismissed = false;
  try { dismissed = localStorage.getItem(TIP_KEY) === '1'; } catch (e) {}
  tip.hidden = dismissed;
  document.getElementById('tip-dismiss').addEventListener('click', function () {
    tip.hidden = true;
    try { localStorage.setItem(TIP_KEY, '1'); } catch (e) {}
  });
})();
