/* @ds-bundle: {"format":4,"namespace":"KepwareMonitorDesignSystem_9e498d","components":[],"sourceHashes":{"handoff/tailwind.preset.js":"aefca0150c50","handoff/tokens.ts":"3967e54b2663","ui_kits/dashboard/components.jsx":"c7a201d30c69","ui_kits/dashboard/icons.jsx":"dea38b846224","ui_kits/dashboard/page_overview.jsx":"0e099dca1cea","ui_kits/dashboard/pages.jsx":"18c0385a0dcb"},"inlinedExternals":[],"unexposedExports":[{"name":"color","sourcePath":"handoff/tokens.ts"},{"name":"font","sourcePath":"handoff/tokens.ts"},{"name":"fontSize","sourcePath":"handoff/tokens.ts"},{"name":"letterSpacing","sourcePath":"handoff/tokens.ts"},{"name":"lineHeight","sourcePath":"handoff/tokens.ts"},{"name":"motion","sourcePath":"handoff/tokens.ts"},{"name":"radius","sourcePath":"handoff/tokens.ts"},{"name":"shadow","sourcePath":"handoff/tokens.ts"},{"name":"spacing","sourcePath":"handoff/tokens.ts"},{"name":"tokens","sourcePath":"handoff/tokens.ts"}]} */

(() => {

const __ds_ns = (window.KepwareMonitorDesignSystem_9e498d = window.KepwareMonitorDesignSystem_9e498d || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// handoff/tailwind.preset.js
try { (() => {
/**
 * Tailwind preset for Kepware Monitor Design System.
 *
 * Usage:
 *   // tailwind.config.js
 *   module.exports = {
 *     presets: [require('./design-system/handoff/tailwind.preset.js')],
 *     content: ['./src/**\/*.{js,jsx,ts,tsx}'],
 *   };
 */
module.exports = {
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: {
          0: '#05070d',
          1: '#0a0f1a',
          2: '#0f172a',
          3: '#172033',
          4: '#1e293b'
        },
        fg: {
          1: '#e6edf7',
          2: '#94a3b8',
          3: '#64748b',
          4: '#3f4b63'
        },
        stroke: {
          1: '#1e293b',
          2: '#293548',
          3: '#3b4a66'
        },
        accent: {
          DEFAULT: '#22d3ee',
          hover: '#06b6d4'
        },
        brand: {
          DEFAULT: '#3b82f6',
          hover: '#2563eb'
        },
        ok: {
          DEFAULT: '#22c55e',
          bg: 'rgba(34,197,94,0.1)'
        },
        warn: {
          DEFAULT: '#f59e0b',
          bg: 'rgba(245,158,11,0.1)'
        },
        err: {
          DEFAULT: '#ef4444',
          bg: 'rgba(239,68,68,0.1)'
        },
        info: {
          DEFAULT: '#60a5fa',
          bg: 'rgba(96,165,250,0.1)'
        },
        muted: {
          DEFAULT: '#475569',
          bg: 'rgba(71,85,105,0.15)'
        }
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'Segoe UI', 'Microsoft JhengHei', 'PingFang TC', 'Noto Sans TC', 'sans-serif'],
        mono: ['JetBrains Mono', 'Cascadia Code', 'Fira Code', 'SF Mono', 'Consolas', 'monospace'],
        display: ['Inter', '-apple-system', 'Microsoft JhengHei', 'sans-serif']
      },
      fontSize: {
        display: ['32px', {
          lineHeight: '1.2',
          letterSpacing: '-0.01em'
        }],
        h1: ['24px', {
          lineHeight: '1.2'
        }],
        h2: ['20px', {
          lineHeight: '1.2'
        }],
        h3: ['16px', {
          lineHeight: '1.5'
        }],
        body: ['14px', {
          lineHeight: '1.5'
        }],
        micro: ['11px', {
          letterSpacing: '0.08em'
        }]
      },
      borderRadius: {
        xs: '4px',
        sm: '6px',
        md: '10px',
        lg: '14px',
        xl: '20px'
      },
      boxShadow: {
        1: '0 2px 6px rgba(0,0,0,0.45), 0 1px 2px rgba(0,0,0,0.3)',
        2: '0 8px 24px rgba(0,0,0,0.5), 0 2px 6px rgba(0,0,0,0.3)',
        3: '0 16px 40px rgba(0,0,0,0.6)',
        'glow-accent': '0 0 0 1px rgba(34,211,238,0.25), 0 0 20px rgba(34,211,238,0.15)',
        'glow-blue': '0 0 0 1px rgba(59,130,246,0.3), 0 0 16px rgba(59,130,246,0.2)'
      },
      transitionTimingFunction: {
        ds: 'cubic-bezier(0.4, 0, 0.2, 1)'
      },
      keyframes: {
        'ds-pulse': {
          '0%,100%': {
            opacity: '1'
          },
          '50%': {
            opacity: '0.55'
          }
        },
        'ds-stripe': {
          to: {
            backgroundPosition: '32px 0'
          }
        }
      },
      animation: {
        'ds-pulse': 'ds-pulse 1.5s ease-in-out infinite',
        'ds-stripe': 'ds-stripe 0.8s linear infinite'
      },
      backgroundImage: {
        'ds-grid': 'linear-gradient(rgba(96,165,250,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(96,165,250,0.05) 1px, transparent 1px)'
      },
      backgroundSize: {
        'ds-grid': '32px 32px'
      }
    }
  }
};
})(); } catch (e) { __ds_ns.__errors.push({ path: "handoff/tailwind.preset.js", error: String((e && e.message) || e) }); }

// handoff/tokens.ts
try { (() => {
/**
 * Kepware Monitor — Design Tokens
 * Generated from colors_and_type.css — keep in sync.
 */

const color = {
  bg: {
    0: '#05070d',
    // app base
    1: '#0a0f1a',
    // page surface
    2: '#0f172a',
    // card
    3: '#172033',
    // elevated / input
    4: '#1e293b',
    // hover
    grid: 'rgba(96, 165, 250, 0.05)'
  },
  fg: {
    1: '#e6edf7',
    // primary
    2: '#94a3b8',
    // secondary / labels
    3: '#64748b',
    // tertiary / placeholder
    4: '#3f4b63' // disabled
  },
  border: {
    1: '#1e293b',
    2: '#293548',
    3: '#3b4a66' // input
  },
  accent: {
    DEFAULT: '#22d3ee',
    hover: '#06b6d4',
    soft: 'rgba(34, 211, 238, 0.12)',
    glow: 'rgba(34, 211, 238, 0.35)'
  },
  blue: {
    DEFAULT: '#3b82f6',
    hover: '#2563eb',
    soft: 'rgba(59, 130, 246, 0.12)',
    glow: 'rgba(59, 130, 246, 0.4)'
  },
  ok: {
    DEFAULT: '#22c55e',
    bg: 'rgba(34, 197, 94, 0.1)',
    glow: 'rgba(34, 197, 94, 0.35)'
  },
  warn: {
    DEFAULT: '#f59e0b',
    bg: 'rgba(245, 158, 11, 0.1)',
    glow: 'rgba(245, 158, 11, 0.35)'
  },
  err: {
    DEFAULT: '#ef4444',
    bg: 'rgba(239, 68, 68, 0.1)',
    glow: 'rgba(239, 68, 68, 0.45)'
  },
  info: {
    DEFAULT: '#60a5fa',
    bg: 'rgba(96, 165, 250, 0.1)'
  },
  muted: {
    DEFAULT: '#475569',
    bg: 'rgba(71, 85, 105, 0.15)'
  }
};
const shadow = {
  sm: '0 1px 2px rgba(0,0,0,0.4)',
  1: '0 2px 6px rgba(0,0,0,0.45), 0 1px 2px rgba(0,0,0,0.3)',
  2: '0 8px 24px rgba(0,0,0,0.5), 0 2px 6px rgba(0,0,0,0.3)',
  3: '0 16px 40px rgba(0,0,0,0.6)',
  glowAccent: '0 0 0 1px rgba(34,211,238,0.25), 0 0 20px rgba(34,211,238,0.15)',
  glowBlue: '0 0 0 1px rgba(59,130,246,0.3), 0 0 16px rgba(59,130,246,0.2)'
};
const radius = {
  xs: '4px',
  sm: '6px',
  md: '10px',
  lg: '14px',
  xl: '20px',
  pill: '999px'
};
const spacing = {
  1: '4px',
  2: '8px',
  3: '12px',
  4: '16px',
  5: '20px',
  6: '24px',
  7: '32px',
  8: '48px',
  9: '64px'
};
const font = {
  sans: '"Inter", -apple-system, "Segoe UI", "Microsoft JhengHei", "PingFang TC", "Noto Sans TC", sans-serif',
  mono: '"JetBrains Mono", "Cascadia Code", "Fira Code", "SF Mono", Consolas, monospace',
  display: '"Inter", -apple-system, "Microsoft JhengHei", sans-serif'
};
const fontSize = {
  display: '32px',
  h1: '24px',
  h2: '20px',
  h3: '16px',
  body: '14px',
  sm: '13px',
  xs: '12px',
  micro: '11px'
};
const lineHeight = {
  tight: 1.2,
  normal: 1.5,
  loose: 1.7
};
const letterSpacing = {
  caps: '0.08em',
  tight: '-0.01em'
};
const motion = {
  ease: 'cubic-bezier(0.4, 0, 0.2, 1)',
  easeOut: 'cubic-bezier(0, 0, 0.2, 1)',
  fast: '120ms',
  med: '200ms',
  slow: '320ms'
};
const tokens = {
  color,
  shadow,
  radius,
  spacing,
  font,
  fontSize,
  lineHeight,
  letterSpacing,
  motion
};
Object.assign(__ds_scope, { color, shadow, radius, spacing, font, fontSize, lineHeight, letterSpacing, motion, tokens, __ds_default_handoff_tokens_1nqh1ni: tokens });
})(); } catch (e) { __ds_ns.__errors.push({ path: "handoff/tokens.ts", error: String((e && e.message) || e) }); }

// ui_kits/dashboard/components.jsx
try { (() => {
// Shared UI primitives for the Kepware dashboard
const {
  useState
} = React;
function Pill({
  kind = 'muted',
  children
}) {
  return /*#__PURE__*/React.createElement("span", {
    className: `pill p-${kind}`
  }, /*#__PURE__*/React.createElement("span", {
    className: "dot"
  }), children);
}
function Dot({
  kind = 'muted'
}) {
  const colors = {
    ok: {
      bg: '#22c55e',
      glow: 'rgba(34,197,94,0.6)'
    },
    warn: {
      bg: '#f59e0b',
      glow: 'rgba(245,158,11,0.6)'
    },
    err: {
      bg: '#ef4444',
      glow: 'rgba(239,68,68,0.8)'
    },
    info: {
      bg: '#60a5fa',
      glow: 'rgba(96,165,250,0.6)'
    },
    muted: {
      bg: '#475569',
      glow: 'rgba(71,85,105,0.4)'
    }
  };
  const c = colors[kind];
  return /*#__PURE__*/React.createElement("span", {
    style: {
      display: 'inline-block',
      width: 9,
      height: 9,
      borderRadius: '50%',
      background: c.bg,
      boxShadow: `0 0 6px ${c.glow}`,
      verticalAlign: 'middle',
      marginRight: 8
    }
  });
}
function Button({
  variant = 'ghost',
  size = 'md',
  icon,
  children,
  onClick
}) {
  const cls = `btn btn-${variant} ${size === 'sm' ? 'btn-sm' : ''}`;
  return /*#__PURE__*/React.createElement("button", {
    className: cls,
    onClick: onClick
  }, icon, children);
}
function Card({
  title,
  icon,
  actions,
  children,
  style
}) {
  return /*#__PURE__*/React.createElement("div", {
    className: "card-ui",
    style: style
  }, title && /*#__PURE__*/React.createElement("div", {
    className: "card-hd"
  }, icon, /*#__PURE__*/React.createElement("span", {
    className: "t"
  }, title), /*#__PURE__*/React.createElement("span", {
    className: "spacer"
  }), actions), children);
}
function Metric({
  title,
  icon,
  value,
  unit,
  delta,
  deltaKind = 'ok',
  active
}) {
  const deltaColor = {
    ok: '#22c55e',
    warn: '#f59e0b',
    err: '#ef4444',
    muted: '#94a3b8'
  }[deltaKind];
  return /*#__PURE__*/React.createElement("div", {
    className: "card-ui",
    style: active ? {
      borderColor: 'rgba(34,211,238,0.35)',
      boxShadow: '0 0 0 1px rgba(34,211,238,0.2), 0 0 24px rgba(34,211,238,0.08)'
    } : {}
  }, /*#__PURE__*/React.createElement("div", {
    className: "card-hd"
  }, icon, /*#__PURE__*/React.createElement("span", {
    className: "t",
    style: active ? {
      color: '#22d3ee'
    } : {}
  }, title)), /*#__PURE__*/React.createElement("div", {
    className: "metric-v"
  }, value, unit && /*#__PURE__*/React.createElement("span", {
    style: {
      fontSize: 14,
      color: '#94a3b8',
      marginLeft: 4,
      fontWeight: 500
    }
  }, unit)), delta && /*#__PURE__*/React.createElement("div", {
    className: "metric-delta",
    style: {
      color: deltaColor
    }
  }, delta));
}
function BrandMark() {
  return /*#__PURE__*/React.createElement("div", {
    className: "brand"
  }, /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 64 64",
    className: "brand-mark"
  }, /*#__PURE__*/React.createElement("rect", {
    x: "2",
    y: "2",
    width: "60",
    height: "60",
    rx: "14",
    fill: "#0f172a",
    stroke: "#22d3ee",
    strokeOpacity: "0.35",
    strokeWidth: "1.5"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "2",
    y: "2",
    width: "60",
    height: "60",
    rx: "14",
    fill: "url(#kpmG)",
    opacity: "0.4"
  }), /*#__PURE__*/React.createElement("text", {
    x: "32",
    y: "40",
    textAnchor: "middle",
    fontFamily: "Inter, sans-serif",
    fontWeight: "800",
    fontSize: "20",
    fill: "#e6edf7",
    letterSpacing: "-0.02em"
  }, "KPM"), /*#__PURE__*/React.createElement("circle", {
    className: "logo-pulse",
    cx: "50",
    cy: "50",
    r: "4",
    fill: "#22d3ee"
  }), /*#__PURE__*/React.createElement("defs", null, /*#__PURE__*/React.createElement("radialGradient", {
    id: "kpmG",
    cx: "0.8",
    cy: "0.2",
    r: "0.9"
  }, /*#__PURE__*/React.createElement("stop", {
    offset: "0",
    stopColor: "#22d3ee",
    stopOpacity: "0.5"
  }), /*#__PURE__*/React.createElement("stop", {
    offset: "1",
    stopColor: "#0f172a",
    stopOpacity: "0"
  })))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    className: "brand-title"
  }, "Kepware"), /*#__PURE__*/React.createElement("div", {
    className: "brand-sub"
  }, "MONITOR")));
}
function Sidebar({
  page,
  setPage,
  alertCount
}) {
  const items = [{
    id: 'overview',
    label: '儀表板',
    en: 'Overview',
    icon: /*#__PURE__*/React.createElement(Icon.dashboard, null)
  }, {
    id: 'channels',
    label: '頻道與設備',
    en: 'Channels',
    icon: /*#__PURE__*/React.createElement(Icon.server, null)
  }, {
    id: 'tags',
    label: '監控點位',
    en: 'Tags',
    icon: /*#__PURE__*/React.createElement(Icon.tag, null)
  }, {
    id: 'alerts',
    label: '告警紀錄',
    en: 'Alerts',
    icon: /*#__PURE__*/React.createElement(Icon.bell, null),
    badge: alertCount
  }, {
    id: 'diag',
    label: '診斷時間軸',
    en: 'Diagnostics',
    icon: /*#__PURE__*/React.createElement(Icon.shield, null)
  }, {
    id: 'history',
    label: '歷史紀錄',
    en: 'History',
    icon: /*#__PURE__*/React.createElement(Icon.clock, null)
  }];
  return /*#__PURE__*/React.createElement("aside", {
    className: "sidebar"
  }, /*#__PURE__*/React.createElement(BrandMark, null), /*#__PURE__*/React.createElement("div", {
    className: "nav-section"
  }, "MONITORING"), items.map(it => /*#__PURE__*/React.createElement("div", {
    key: it.id,
    className: `nav-item ${page === it.id ? 'active' : ''}`,
    onClick: () => setPage(it.id)
  }, it.icon, /*#__PURE__*/React.createElement("span", null, it.label), it.badge ? /*#__PURE__*/React.createElement("span", {
    className: "badge"
  }, it.badge) : null)), /*#__PURE__*/React.createElement("div", {
    className: "nav-section"
  }, "SYSTEM"), /*#__PURE__*/React.createElement("div", {
    className: "nav-item"
  }, /*#__PURE__*/React.createElement(Icon.settings, null), /*#__PURE__*/React.createElement("span", null, "\u8A2D\u5B9A")));
}
function Topbar({
  page
}) {
  const titles = {
    overview: {
      h1: '設備監控儀表板',
      crumb: 'home / overview'
    },
    channels: {
      h1: '頻道與設備',
      crumb: 'home / channels'
    },
    tags: {
      h1: '監控點位 · Tags',
      crumb: 'home / tags'
    },
    alerts: {
      h1: '告警紀錄',
      crumb: 'home / alerts'
    },
    diag: {
      h1: '三層網路診斷',
      crumb: 'home / diagnostics'
    },
    history: {
      h1: '歷史資料查詢',
      crumb: 'home / history'
    }
  };
  const t = titles[page];
  return /*#__PURE__*/React.createElement("header", {
    className: "topbar"
  }, /*#__PURE__*/React.createElement("div", {
    className: "title"
  }, /*#__PURE__*/React.createElement("h1", null, t.h1), /*#__PURE__*/React.createElement("div", {
    className: "crumbs"
  }, t.crumb)), /*#__PURE__*/React.createElement("span", {
    className: "top-spacer"
  }), /*#__PURE__*/React.createElement("div", {
    className: "top-meta"
  }, /*#__PURE__*/React.createElement("div", {
    className: "poll"
  }, /*#__PURE__*/React.createElement("span", {
    className: "dot"
  }), "LIVE \xB7 next poll 04:12"), /*#__PURE__*/React.createElement(Button, {
    variant: "ghost",
    size: "sm",
    icon: /*#__PURE__*/React.createElement(Icon.search, null)
  }, "\u641C\u5C0B"), /*#__PURE__*/React.createElement("div", {
    className: "avatar"
  }, "OP")));
}
Object.assign(window, {
  Pill,
  Dot,
  Button,
  Card,
  Metric,
  BrandMark,
  Sidebar,
  Topbar
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/dashboard/components.jsx", error: String((e && e.message) || e) }); }

// ui_kits/dashboard/icons.jsx
try { (() => {
function _extends() { return _extends = Object.assign ? Object.assign.bind() : function (n) { for (var e = 1; e < arguments.length; e++) { var t = arguments[e]; for (var r in t) ({}).hasOwnProperty.call(t, r) && (n[r] = t[r]); } return n; }, _extends.apply(null, arguments); }
// Icons — minimal Lucide subset used by the dashboard
const Icon = {
  dashboard: p => /*#__PURE__*/React.createElement("svg", _extends({}, p, {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "3",
    y: "3",
    width: "7",
    height: "7"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "14",
    y: "3",
    width: "7",
    height: "7"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "14",
    y: "14",
    width: "7",
    height: "7"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "3",
    y: "14",
    width: "7",
    height: "7"
  })),
  server: p => /*#__PURE__*/React.createElement("svg", _extends({}, p, {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "2",
    y: "2",
    width: "20",
    height: "8",
    rx: "2"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "2",
    y: "14",
    width: "20",
    height: "8",
    rx: "2"
  }), /*#__PURE__*/React.createElement("line", {
    x1: "6",
    y1: "6",
    x2: "6.01",
    y2: "6"
  }), /*#__PURE__*/React.createElement("line", {
    x1: "6",
    y1: "18",
    x2: "6.01",
    y2: "18"
  })),
  tag: p => /*#__PURE__*/React.createElement("svg", _extends({}, p, {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"
  }), /*#__PURE__*/React.createElement("line", {
    x1: "7",
    y1: "7",
    x2: "7.01",
    y2: "7"
  })),
  bell: p => /*#__PURE__*/React.createElement("svg", _extends({}, p, {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M13.73 21a2 2 0 0 1-3.46 0"
  })),
  shield: p => /*#__PURE__*/React.createElement("svg", _extends({}, p, {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"
  })),
  clock: p => /*#__PURE__*/React.createElement("svg", _extends({}, p, {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "12",
    cy: "12",
    r: "10"
  }), /*#__PURE__*/React.createElement("polyline", {
    points: "12 6 12 12 16 14"
  })),
  settings: p => /*#__PURE__*/React.createElement("svg", _extends({}, p, {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "12",
    cy: "12",
    r: "3"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"
  })),
  search: p => /*#__PURE__*/React.createElement("svg", _extends({}, p, {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "11",
    cy: "11",
    r: "8"
  }), /*#__PURE__*/React.createElement("line", {
    x1: "21",
    y1: "21",
    x2: "16.65",
    y2: "16.65"
  })),
  download: p => /*#__PURE__*/React.createElement("svg", _extends({}, p, {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"
  }), /*#__PURE__*/React.createElement("polyline", {
    points: "7 10 12 15 17 10"
  }), /*#__PURE__*/React.createElement("line", {
    x1: "12",
    y1: "15",
    x2: "12",
    y2: "3"
  })),
  upload: p => /*#__PURE__*/React.createElement("svg", _extends({}, p, {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"
  }), /*#__PURE__*/React.createElement("polyline", {
    points: "17 8 12 3 7 8"
  }), /*#__PURE__*/React.createElement("line", {
    x1: "12",
    y1: "3",
    x2: "12",
    y2: "15"
  })),
  plus: p => /*#__PURE__*/React.createElement("svg", _extends({}, p, {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }), /*#__PURE__*/React.createElement("line", {
    x1: "12",
    y1: "5",
    x2: "12",
    y2: "19"
  }), /*#__PURE__*/React.createElement("line", {
    x1: "5",
    y1: "12",
    x2: "19",
    y2: "12"
  })),
  trash: p => /*#__PURE__*/React.createElement("svg", _extends({}, p, {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }), /*#__PURE__*/React.createElement("polyline", {
    points: "3 6 5 6 21 6"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"
  })),
  activity: p => /*#__PURE__*/React.createElement("svg", _extends({}, p, {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }), /*#__PURE__*/React.createElement("polyline", {
    points: "22 12 18 12 15 21 9 3 6 12 2 12"
  })),
  alert: p => /*#__PURE__*/React.createElement("svg", _extends({}, p, {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "12",
    cy: "12",
    r: "10"
  }), /*#__PURE__*/React.createElement("line", {
    x1: "12",
    y1: "8",
    x2: "12",
    y2: "12"
  }), /*#__PURE__*/React.createElement("line", {
    x1: "12",
    y1: "16",
    x2: "12.01",
    y2: "16"
  })),
  check: p => /*#__PURE__*/React.createElement("svg", _extends({}, p, {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }), /*#__PURE__*/React.createElement("polyline", {
    points: "20 6 9 17 4 12"
  })),
  x: p => /*#__PURE__*/React.createElement("svg", _extends({}, p, {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }), /*#__PURE__*/React.createElement("line", {
    x1: "18",
    y1: "6",
    x2: "6",
    y2: "18"
  }), /*#__PURE__*/React.createElement("line", {
    x1: "6",
    y1: "6",
    x2: "18",
    y2: "18"
  })),
  chevR: p => /*#__PURE__*/React.createElement("svg", _extends({}, p, {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }), /*#__PURE__*/React.createElement("polyline", {
    points: "9 18 15 12 9 6"
  })),
  cpu: p => /*#__PURE__*/React.createElement("svg", _extends({}, p, {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "4",
    y: "4",
    width: "16",
    height: "16",
    rx: "2"
  }), /*#__PURE__*/React.createElement("rect", {
    x: "9",
    y: "9",
    width: "6",
    height: "6"
  }), /*#__PURE__*/React.createElement("line", {
    x1: "9",
    y1: "2",
    x2: "9",
    y2: "4"
  }), /*#__PURE__*/React.createElement("line", {
    x1: "15",
    y1: "2",
    x2: "15",
    y2: "4"
  }), /*#__PURE__*/React.createElement("line", {
    x1: "9",
    y1: "20",
    x2: "9",
    y2: "22"
  }), /*#__PURE__*/React.createElement("line", {
    x1: "15",
    y1: "20",
    x2: "15",
    y2: "22"
  }), /*#__PURE__*/React.createElement("line", {
    x1: "2",
    y1: "9",
    x2: "4",
    y2: "9"
  }), /*#__PURE__*/React.createElement("line", {
    x1: "2",
    y1: "15",
    x2: "4",
    y2: "15"
  }), /*#__PURE__*/React.createElement("line", {
    x1: "20",
    y1: "9",
    x2: "22",
    y2: "9"
  }), /*#__PURE__*/React.createElement("line", {
    x1: "20",
    y1: "15",
    x2: "22",
    y2: "15"
  })),
  net: p => /*#__PURE__*/React.createElement("svg", _extends({}, p, {
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "2",
    strokeLinecap: "round",
    strokeLinejoin: "round"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "12",
    cy: "12",
    r: "10"
  }), /*#__PURE__*/React.createElement("line", {
    x1: "2",
    y1: "12",
    x2: "22",
    y2: "12"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"
  }))
};
window.Icon = Icon;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/dashboard/icons.jsx", error: String((e && e.message) || e) }); }

// ui_kits/dashboard/page_overview.jsx
try { (() => {
// Page: Overview
const {
  useState: useStateOv
} = React;
function PageOverview() {
  const alerts = [{
    sev: 'err',
    who: 'kepware_a · iFIX3_SecondError',
    msg: 'VALUE_ABNORMAL · 124s since last error (threshold < 60s)',
    time: '14:32:09'
  }, {
    sev: 'err',
    who: 'kepware_a · 主機 192.168.1.10',
    msg: 'L1 HOST_DOWN · Ping 失敗 · 派報 IT',
    time: '14:28:41'
  }, {
    sev: 'warn',
    who: 'kepware_b · iFIX7_SecondError',
    msg: 'counter 2/3 · 累積次數將達標',
    time: '14:25:03'
  }];
  const devices = [{
    name: 'kepware_a',
    host: '192.168.1.10',
    status: 'ok',
    tags: 42,
    alerts: 1
  }, {
    name: 'kepware_b',
    host: '192.168.1.11',
    status: 'warn',
    tags: 38,
    alerts: 0
  }, {
    name: 'kepware_c',
    host: '192.168.1.12',
    status: 'err',
    tags: 62,
    alerts: 2
  }, {
    name: 'kepware_d',
    host: '192.168.1.13',
    status: 'ok',
    tags: 24,
    alerts: 0
  }];
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "banner err"
  }, /*#__PURE__*/React.createElement("div", {
    className: "banner-icon"
  }, /*#__PURE__*/React.createElement(Icon.alert, null)), /*#__PURE__*/React.createElement("div", {
    className: "banner-body"
  }, /*#__PURE__*/React.createElement("h4", null, "[\u9023\u7DDA\u7570\u5E38] kepware_a OPC \u670D\u52D9\u7570\u5E38"), /*#__PURE__*/React.createElement("p", null, "L1 HOST_DOWN \xB7 192.168.1.10 \xB7 \u5DF2\u6D3E\u5831\u81F3 IT \u7FA4\u7D44 \xB7 \u6301\u7E8C 00:04:12")), /*#__PURE__*/React.createElement(Button, {
    variant: "outline",
    size: "sm"
  }, "\u67E5\u770B\u8A3A\u65B7"), /*#__PURE__*/React.createElement(Button, {
    variant: "ghost",
    size: "sm"
  }, "\u66AB\u6642\u975C\u97F3")), /*#__PURE__*/React.createElement("div", {
    className: "metrics"
  }, /*#__PURE__*/React.createElement(Metric, {
    title: "Active Servers",
    icon: /*#__PURE__*/React.createElement(Icon.server, null),
    value: "4",
    delta: "all reachable",
    deltaKind: "ok"
  }), /*#__PURE__*/React.createElement(Metric, {
    title: "Monitored Tags",
    icon: /*#__PURE__*/React.createElement(Icon.tag, null),
    value: "166",
    unit: "points",
    delta: "\u25B2 3 loaded from CSV",
    deltaKind: "muted"
  }), /*#__PURE__*/React.createElement(Metric, {
    title: "Active Alerts",
    icon: /*#__PURE__*/React.createElement(Icon.bell, null),
    value: "3",
    delta: "1 new in last 5 min",
    deltaKind: "err",
    active: true
  }), /*#__PURE__*/React.createElement(Metric, {
    title: "Next Poll",
    icon: /*#__PURE__*/React.createElement(Icon.clock, null),
    value: "04:12",
    delta: "interval 600s",
    deltaKind: "muted"
  })), /*#__PURE__*/React.createElement("div", {
    className: "two-col"
  }, /*#__PURE__*/React.createElement(Card, {
    title: "KEPWARE SERVERS",
    icon: /*#__PURE__*/React.createElement(Icon.server, null),
    actions: /*#__PURE__*/React.createElement(Button, {
      variant: "ghost",
      size: "sm"
    }, "\u5168\u90E8\u6AA2\u8996")
  }, /*#__PURE__*/React.createElement("div", {
    className: "tbl-wrap"
  }, /*#__PURE__*/React.createElement("table", null, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "Server"), /*#__PURE__*/React.createElement("th", null, "Host"), /*#__PURE__*/React.createElement("th", {
    className: "td-num"
  }, "Tags"), /*#__PURE__*/React.createElement("th", null, "Status"), /*#__PURE__*/React.createElement("th", null, "Alerts"))), /*#__PURE__*/React.createElement("tbody", null, devices.map(d => /*#__PURE__*/React.createElement("tr", {
    key: d.name
  }, /*#__PURE__*/React.createElement("td", {
    style: {
      fontWeight: 600
    }
  }, /*#__PURE__*/React.createElement(Dot, {
    kind: d.status
  }), d.name), /*#__PURE__*/React.createElement("td", {
    className: "td-mono"
  }, d.host, ":49320"), /*#__PURE__*/React.createElement("td", {
    className: "td-num"
  }, d.tags), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Pill, {
    kind: d.status
  }, d.status === 'ok' ? 'CONNECTED' : d.status === 'warn' ? 'DEGRADED' : 'HOST_DOWN')), /*#__PURE__*/React.createElement("td", {
    className: "td-mono",
    style: {
      color: d.alerts ? '#ef4444' : '#64748b'
    }
  }, d.alerts || '—'))))))), /*#__PURE__*/React.createElement(Card, {
    title: "ACTIVE ALERTS",
    icon: /*#__PURE__*/React.createElement(Icon.bell, null),
    actions: /*#__PURE__*/React.createElement(Button, {
      variant: "ghost",
      size: "sm"
    }, "Manage")
  }, alerts.map((a, i) => /*#__PURE__*/React.createElement("div", {
    key: i,
    className: "diag"
  }, /*#__PURE__*/React.createElement("div", {
    className: `diag-icon ${a.sev}`
  }, /*#__PURE__*/React.createElement(Icon.alert, null)), /*#__PURE__*/React.createElement("div", {
    className: "diag-body"
  }, /*#__PURE__*/React.createElement("div", {
    className: "who"
  }, a.who), /*#__PURE__*/React.createElement("div", {
    className: "msg"
  }, a.msg)), /*#__PURE__*/React.createElement("div", {
    className: "diag-time"
  }, a.time))))), /*#__PURE__*/React.createElement(Card, {
    title: "POLLING LOG \xB7 kepware_a",
    icon: /*#__PURE__*/React.createElement(Icon.activity, null),
    actions: /*#__PURE__*/React.createElement(Button, {
      variant: "ghost",
      size: "sm",
      icon: /*#__PURE__*/React.createElement(Icon.download, null)
    }, "Export")
  }, /*#__PURE__*/React.createElement("div", {
    className: "log"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "t"
  }, "14:32:07"), " ", /*#__PURE__*/React.createElement("span", {
    className: "i"
  }, "[kepware_a]"), " \u8B80\u53D6 42 \u500B\u9EDE\u4F4D\u2026"), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "t"
  }, "14:32:08"), " ", /*#__PURE__*/React.createElement("span", {
    className: "o"
  }, "[OK]"), " iFIX1_SecondError = 12"), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "t"
  }, "14:32:08"), " ", /*#__PURE__*/React.createElement("span", {
    className: "w"
  }, "[WARN]"), " iFIX2_SecondError = 58 (counter 2/3)"), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "t"
  }, "14:32:09"), " ", /*#__PURE__*/React.createElement("span", {
    className: "e"
  }, "[ALERT]"), " iFIX3_SecondError \u89F8\u767C\u7570\u5E38 > 60s \xB7 \u7D2F\u7A4D 3/3"), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "t"
  }, "14:32:09"), " ", /*#__PURE__*/React.createElement("span", {
    className: "i"
  }, "[L3 DIAG]"), " iFIX/IGS \u6A5F\u53F0 10.0.1.20 \u7121\u6CD5\u9023\u7DDA (Ping \u5931\u6557)"), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "t"
  }, "14:32:10"), " ", /*#__PURE__*/React.createElement("span", {
    className: "i"
  }, ">>> \u5BC4\u9001\u4FE1\u4EF6:"), " [\u7570\u5E38] Kepware \u8A2D\u5099\u76E3\u63A7\u901A\u77E5 - iFIX3_SecondError"), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "t"
  }, "14:32:10"), " ", /*#__PURE__*/React.createElement("span", {
    className: "o"
  }, "[SENT]"), " ops@factory.com, ops-lead@factory.com"), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "t"
  }, "14:32:11"), " ", /*#__PURE__*/React.createElement("span", {
    className: "o"
  }, "[DB]"), " monitor_history \u2190 42 rows (alert_log \u2190 1 row)"))));
}
window.PageOverview = PageOverview;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/dashboard/page_overview.jsx", error: String((e && e.message) || e) }); }

// ui_kits/dashboard/pages.jsx
try { (() => {
// Pages: Channels, Tags, Alerts, Diagnostics, History
const {
  useState: useStateP
} = React;

/* ---------------- CHANNELS ---------------- */
function PageChannels() {
  const [open, setOpen] = useStateP(['kepware_a']);
  const tree = [{
    name: 'kepware_a',
    host: '192.168.1.10',
    status: 'warn',
    channels: [{
      name: 'Channel1',
      devices: [{
        name: 'iFIX1',
        ip: '10.0.1.10',
        status: 'ok',
        tags: 8
      }, {
        name: 'iFIX2',
        ip: '10.0.1.11',
        status: 'warn',
        tags: 8
      }, {
        name: 'iFIX3',
        ip: '10.0.1.20',
        status: 'err',
        tags: 8
      }]
    }, {
      name: 'Channel2',
      devices: [{
        name: 'Device1',
        ip: '10.0.1.30',
        status: 'ok',
        tags: 12
      }]
    }]
  }, {
    name: 'kepware_b',
    host: '192.168.1.11',
    status: 'ok',
    channels: []
  }, {
    name: 'kepware_c',
    host: '192.168.1.12',
    status: 'err',
    channels: []
  }];
  const tag = o => open.includes(o) ? open.filter(x => x !== o) : [...open, o];
  const [selected] = useStateP('Channel1.iFIX3');
  return /*#__PURE__*/React.createElement("div", {
    className: "two-col",
    style: {
      gridTemplateColumns: '360px 1fr'
    }
  }, /*#__PURE__*/React.createElement(Card, {
    title: "SERVER TREE",
    icon: /*#__PURE__*/React.createElement(Icon.server, null),
    actions: /*#__PURE__*/React.createElement(Button, {
      variant: "ghost",
      size: "sm",
      icon: /*#__PURE__*/React.createElement(Icon.search, null)
    })
  }, tree.map(s => /*#__PURE__*/React.createElement("div", {
    key: s.name
  }, /*#__PURE__*/React.createElement("div", {
    className: `tree-row ${open.includes(s.name) ? 'open' : ''}`,
    onClick: () => setOpen(tag(s.name))
  }, /*#__PURE__*/React.createElement(Icon.chevR, {
    className: "chev"
  }), /*#__PURE__*/React.createElement(Icon.server, {
    style: {
      width: 15,
      height: 15,
      color: '#22d3ee'
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      fontWeight: 600
    }
  }, s.name), /*#__PURE__*/React.createElement(Dot, {
    kind: s.status
  }), /*#__PURE__*/React.createElement("span", {
    className: "count"
  }, s.channels.reduce((a, c) => a + c.devices.length, 0))), open.includes(s.name) && s.channels.map(ch => /*#__PURE__*/React.createElement("div", {
    key: ch.name,
    className: "tree-child"
  }, /*#__PURE__*/React.createElement("div", {
    className: "tree-row",
    style: {
      padding: '7px 10px',
      fontSize: 12.5
    }
  }, /*#__PURE__*/React.createElement(Icon.net, {
    style: {
      width: 13,
      height: 13,
      color: '#94a3b8'
    }
  }), /*#__PURE__*/React.createElement("span", {
    style: {
      color: '#94a3b8'
    }
  }, ch.name), /*#__PURE__*/React.createElement("span", {
    className: "count"
  }, ch.devices.length)), ch.devices.map(d => /*#__PURE__*/React.createElement("div", {
    key: d.name,
    className: `tree-row ${selected.endsWith(d.name) ? 'active' : ''}`,
    style: {
      padding: '7px 10px 7px 24px',
      fontSize: 12.5
    }
  }, /*#__PURE__*/React.createElement(Icon.cpu, {
    style: {
      width: 13,
      height: 13
    }
  }), /*#__PURE__*/React.createElement("span", {
    className: "td-mono",
    style: {
      fontSize: 12
    }
  }, d.name), /*#__PURE__*/React.createElement(Dot, {
    kind: d.status
  }), /*#__PURE__*/React.createElement("span", {
    className: "count"
  }, d.tags)))))))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(Card, {
    title: "DEVICE \xB7 Channel1.iFIX3",
    icon: /*#__PURE__*/React.createElement(Icon.cpu, null),
    actions: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
      variant: "ghost",
      size: "sm",
      icon: /*#__PURE__*/React.createElement(Icon.activity, null)
    }, "Test ping"), /*#__PURE__*/React.createElement(Button, {
      variant: "accent",
      size: "sm",
      icon: /*#__PURE__*/React.createElement(Icon.plus, null)
    }, "\u65B0\u589E\u9EDE\u4F4D"))
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(3,1fr)',
      gap: 20,
      marginBottom: 18
    }
  }, /*#__PURE__*/React.createElement(Field, {
    label: "IP",
    value: "10.0.1.20"
  }), /*#__PURE__*/React.createElement(Field, {
    label: "IGS Port",
    value: "49310"
  }), /*#__PURE__*/React.createElement(Field, {
    label: "Connection",
    value: /*#__PURE__*/React.createElement(Pill, {
      kind: "err"
    }, "L3 IGS_DOWN")
  }), /*#__PURE__*/React.createElement(Field, {
    label: "Last poll",
    value: "14:32:09"
  }), /*#__PURE__*/React.createElement(Field, {
    label: "Tags",
    value: "8 monitored / 1 alert"
  }), /*#__PURE__*/React.createElement(Field, {
    label: "Mail to",
    value: "ops@factory.com"
  })), /*#__PURE__*/React.createElement("div", {
    className: "tbl-wrap"
  }, /*#__PURE__*/React.createElement("table", null, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "Tag"), /*#__PURE__*/React.createElement("th", null, "NodeId"), /*#__PURE__*/React.createElement("th", null, "Type"), /*#__PURE__*/React.createElement("th", null, "Condition"), /*#__PURE__*/React.createElement("th", {
    className: "td-num"
  }, "Value"), /*#__PURE__*/React.createElement("th", null, "Status"))), /*#__PURE__*/React.createElement("tbody", null, /*#__PURE__*/React.createElement(TagRow, {
    name: "iFIX3_SecondError",
    nid: "ns=2;s=Channel1.iFIX3._System._Sec",
    cond: "less < 60",
    v: "124",
    s: "err",
    badge: "VALUE_ABNORMAL"
  }), /*#__PURE__*/React.createElement(TagRow, {
    name: "iFIX3_Heartbeat",
    nid: "ns=2;s=Channel1.iFIX3.Heartbeat",
    cond: "equal = 1",
    v: "1",
    s: "ok",
    badge: "OK"
  }), /*#__PURE__*/React.createElement(TagRow, {
    name: "iFIX3_Temp1",
    nid: "ns=2;s=Channel1.iFIX3.T1",
    cond: "greater > 85",
    v: "42.7",
    s: "ok",
    badge: "OK"
  }), /*#__PURE__*/React.createElement(TagRow, {
    name: "iFIX3_Pressure",
    nid: "ns=2;s=Channel1.iFIX3.P",
    cond: "less < 0",
    v: "3.1",
    s: "ok",
    badge: "OK"
  }), /*#__PURE__*/React.createElement(TagRow, {
    name: "iFIX3_Counter",
    nid: "ns=2;s=Channel1.iFIX3.CT",
    cond: "log only",
    v: "1,284",
    s: "info",
    badge: "LOG_ONLY"
  })))))));
}
function Field({
  label,
  value
}) {
  return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: '#64748b',
      textTransform: 'uppercase',
      letterSpacing: '0.08em',
      fontWeight: 600,
      marginBottom: 4
    }
  }, label), /*#__PURE__*/React.createElement("div", {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: 13,
      color: '#e6edf7'
    }
  }, value));
}
function TagRow({
  name,
  nid,
  cond,
  v,
  s,
  badge
}) {
  return /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Dot, {
    kind: s
  }), name), /*#__PURE__*/React.createElement("td", {
    className: "td-mono"
  }, nid), /*#__PURE__*/React.createElement("td", {
    className: "td-mono"
  }, "FLOAT"), /*#__PURE__*/React.createElement("td", {
    className: "td-mono"
  }, cond), /*#__PURE__*/React.createElement("td", {
    className: "td-num",
    style: {
      color: s === 'err' ? '#ef4444' : '#e6edf7',
      fontWeight: 600
    }
  }, v), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Pill, {
    kind: s
  }, badge)));
}

/* ---------------- TAGS (+CSV) ---------------- */
function PageTags() {
  const [tab, setTab] = useStateP('list');
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "section-hd"
  }, /*#__PURE__*/React.createElement("h2", null, "\u76E3\u63A7\u9EDE\u4F4D"), /*#__PURE__*/React.createElement("span", {
    className: "count"
  }, "166 tags"), /*#__PURE__*/React.createElement("div", {
    className: "actions"
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "ghost",
    icon: /*#__PURE__*/React.createElement(Icon.download, null)
  }, "\u4E0B\u8F09\u7BC4\u672C"), /*#__PURE__*/React.createElement(Button, {
    variant: "outline",
    icon: /*#__PURE__*/React.createElement(Icon.upload, null),
    onClick: () => setTab('csv')
  }, "CSV \u532F\u5165"), /*#__PURE__*/React.createElement(Button, {
    variant: "primary",
    icon: /*#__PURE__*/React.createElement(Icon.plus, null)
  }, "\u65B0\u589E\u9EDE\u4F4D"))), /*#__PURE__*/React.createElement("div", {
    className: "ctabs"
  }, /*#__PURE__*/React.createElement("div", {
    className: `ctab ${tab === 'list' ? 'active' : ''}`,
    onClick: () => setTab('list')
  }, /*#__PURE__*/React.createElement(Icon.tag, null), "\u5168\u90E8\u9EDE\u4F4D"), /*#__PURE__*/React.createElement("div", {
    className: `ctab ${tab === 'csv' ? 'active' : ''}`,
    onClick: () => setTab('csv')
  }, /*#__PURE__*/React.createElement(Icon.upload, null), "CSV \u532F\u5165"), /*#__PURE__*/React.createElement("div", {
    className: `ctab ${tab === 'thr' ? 'active' : ''}`,
    onClick: () => setTab('thr')
  }, /*#__PURE__*/React.createElement(Icon.shield, null), "\u95BE\u503C\u8A2D\u5B9A")), tab === 'list' && /*#__PURE__*/React.createElement(TagsList, null), tab === 'csv' && /*#__PURE__*/React.createElement(CsvImport, null), tab === 'thr' && /*#__PURE__*/React.createElement(ThresholdMatrix, null));
}
function TagsList() {
  return /*#__PURE__*/React.createElement(Card, null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 12,
      marginBottom: 14
    }
  }, /*#__PURE__*/React.createElement("div", {
    className: "search",
    style: {
      flex: 1
    }
  }, /*#__PURE__*/React.createElement(Icon.search, null), /*#__PURE__*/React.createElement("input", {
    className: "input",
    placeholder: "\u641C\u5C0B tag name\u3001NodeId \u6216\u8A2D\u5099\u2026"
  })), /*#__PURE__*/React.createElement("select", {
    className: "select"
  }, /*#__PURE__*/React.createElement("option", null, "\u5168\u90E8 Server"), /*#__PURE__*/React.createElement("option", null, "kepware_a")), /*#__PURE__*/React.createElement("select", {
    className: "select"
  }, /*#__PURE__*/React.createElement("option", null, "\u5168\u90E8\u72C0\u614B"), /*#__PURE__*/React.createElement("option", null, "\u7570\u5E38"))), /*#__PURE__*/React.createElement("div", {
    className: "tbl-wrap"
  }, /*#__PURE__*/React.createElement("table", null, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
    style: {
      width: 30
    }
  }, /*#__PURE__*/React.createElement("input", {
    type: "checkbox"
  })), /*#__PURE__*/React.createElement("th", null, "Tag"), /*#__PURE__*/React.createElement("th", null, "Server"), /*#__PURE__*/React.createElement("th", null, "NodeId"), /*#__PURE__*/React.createElement("th", null, "Condition"), /*#__PURE__*/React.createElement("th", {
    className: "td-num"
  }, "Threshold"), /*#__PURE__*/React.createElement("th", {
    className: "td-num"
  }, "CountNeeded"), /*#__PURE__*/React.createElement("th", null, "Mail"), /*#__PURE__*/React.createElement("th", null, "Status"))), /*#__PURE__*/React.createElement("tbody", null, [['iFIX1_SecondError', 'kepware_a', 'ns=2;s=Channel1.iFIX1._Sys._Sec', 'less', 60, 3, 'ops@factory.com', 'ok', 'OK'], ['iFIX2_SecondError', 'kepware_a', 'ns=2;s=Channel1.iFIX2._Sys._Sec', 'less', 60, 3, 'ops@factory.com', 'warn', '2/3'], ['iFIX3_SecondError', 'kepware_a', 'ns=2;s=Channel1.iFIX3._Sys._Sec', 'less', 60, 3, 'ops@factory.com; lead@', 'err', 'FIRED'], ['iFIX3_Temp1', 'kepware_a', 'ns=2;s=Channel1.iFIX3.T1', 'greater', 85, 1, 'ops@factory.com', 'ok', 'OK'], ['LogOnly_Counter', 'kepware_a', 'ns=2;s=Channel1.iFIX3.CT', '—', '—', '—', '(log only)', 'info', 'LOG'], ['Boiler_Pressure', 'kepware_b', 'ns=2;s=Ch1.Dev1.Pressure', 'greater', '12.5', 2, 'boiler@factory.com', 'ok', 'OK'], ['Boiler_Temp', 'kepware_b', 'ns=2;s=Ch1.Dev1.Temp', 'greater', 200, 2, 'boiler@factory.com', 'ok', 'OK'], ['Line3_StopFlag', 'kepware_c', 'ns=2;s=Ch1.L3.Stop', 'equal', 1, 1, 'line3@factory.com', 'err', 'FIRED'], ['Line3_CycleCount', 'kepware_c', 'ns=2;s=Ch1.L3.CC', '—', '—', '—', '(log only)', 'muted', 'DISABLED']].map((r, i) => /*#__PURE__*/React.createElement("tr", {
    key: i
  }, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("input", {
    type: "checkbox"
  })), /*#__PURE__*/React.createElement("td", {
    style: {
      fontWeight: 600
    }
  }, /*#__PURE__*/React.createElement(Dot, {
    kind: r[7]
  }), r[0]), /*#__PURE__*/React.createElement("td", {
    className: "td-mono"
  }, r[1]), /*#__PURE__*/React.createElement("td", {
    className: "td-mono",
    style: {
      maxWidth: 240,
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap'
    }
  }, r[2]), /*#__PURE__*/React.createElement("td", {
    className: "td-mono"
  }, r[3]), /*#__PURE__*/React.createElement("td", {
    className: "td-num"
  }, r[4]), /*#__PURE__*/React.createElement("td", {
    className: "td-num"
  }, r[5]), /*#__PURE__*/React.createElement("td", {
    className: "td-mono",
    style: {
      maxWidth: 180,
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap'
    }
  }, r[6]), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Pill, {
    kind: r[7]
  }, r[8]))))))));
}
function CsvImport() {
  return /*#__PURE__*/React.createElement("div", {
    className: "two-col"
  }, /*#__PURE__*/React.createElement(Card, {
    title: "UPLOAD",
    icon: /*#__PURE__*/React.createElement(Icon.upload, null)
  }, /*#__PURE__*/React.createElement("div", {
    className: "upload"
  }, /*#__PURE__*/React.createElement(Icon.upload, null), /*#__PURE__*/React.createElement("h4", null, "\u62D6\u66F3 tags.csv \u5230\u6B64\u8655"), /*#__PURE__*/React.createElement("p", {
    style: {
      marginBottom: 12
    }
  }, "\u6216\u9EDE\u64CA\u9078\u64C7\u6A94\u6848 \xB7 \u6B04\u4F4D: name, nodeid, server, type, condition, threshold, countneeded, enable, device_ip, device_port, mail_to, mail_cc"), /*#__PURE__*/React.createElement(Button, {
    variant: "outline",
    size: "sm",
    icon: /*#__PURE__*/React.createElement(Icon.download, null)
  }, "\u4E0B\u8F09\u7BC4\u672C")), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 16,
      display: 'flex',
      alignItems: 'center',
      gap: 10
    }
  }, /*#__PURE__*/React.createElement("input", {
    type: "checkbox",
    defaultChecked: true,
    style: {
      accentColor: '#22d3ee'
    },
    id: "dry"
  }), /*#__PURE__*/React.createElement("label", {
    htmlFor: "dry",
    style: {
      color: '#fde68a',
      fontSize: 13
    }
  }, "DRY RUN \xB7 \u9810\u6F14\uFF0C\u4E0D\u6703\u771F\u7684\u5BEB\u5165"))), /*#__PURE__*/React.createElement(Card, {
    title: "PREVIEW \xB7 3 rows parsed",
    icon: /*#__PURE__*/React.createElement(Icon.check, null),
    actions: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
      variant: "ghost",
      size: "sm"
    }, "\u53D6\u6D88"), /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "sm",
      icon: /*#__PURE__*/React.createElement(Icon.check, null)
    }, "DRY RUN"), /*#__PURE__*/React.createElement(Button, {
      variant: "danger",
      size: "sm"
    }, "\u57F7\u884C LIVE"))
  }, /*#__PURE__*/React.createElement("div", {
    className: "tbl-wrap"
  }, /*#__PURE__*/React.createElement("table", null, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "#"), /*#__PURE__*/React.createElement("th", null, "name"), /*#__PURE__*/React.createElement("th", null, "condition"), /*#__PURE__*/React.createElement("th", {
    className: "td-num"
  }, "thr"), /*#__PURE__*/React.createElement("th", null, "result"))), /*#__PURE__*/React.createElement("tbody", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
    className: "td-mono"
  }, "1"), /*#__PURE__*/React.createElement("td", null, "Line4_Temp"), /*#__PURE__*/React.createElement("td", {
    className: "td-mono"
  }, "greater > 75"), /*#__PURE__*/React.createElement("td", {
    className: "td-num"
  }, "75"), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Pill, {
    kind: "ok"
  }, "\u65B0\u589E"))), /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
    className: "td-mono"
  }, "2"), /*#__PURE__*/React.createElement("td", null, "Line4_Pres"), /*#__PURE__*/React.createElement("td", {
    className: "td-mono"
  }, "less < 1.0"), /*#__PURE__*/React.createElement("td", {
    className: "td-num"
  }, "1.0"), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Pill, {
    kind: "ok"
  }, "\u65B0\u589E"))), /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
    className: "td-mono"
  }, "3"), /*#__PURE__*/React.createElement("td", null, "iFIX3_Temp1"), /*#__PURE__*/React.createElement("td", {
    className: "td-mono"
  }, "greater > 85"), /*#__PURE__*/React.createElement("td", {
    className: "td-num"
  }, "85"), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Pill, {
    kind: "warn"
  }, "\u8986\u84CB\u65E2\u6709")))))), /*#__PURE__*/React.createElement("div", {
    className: "log",
    style: {
      marginTop: 14
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "t"
  }, "14:33:02"), " ", /*#__PURE__*/React.createElement("span", {
    className: "i"
  }, "[CSV]"), " \u8B80\u53D6 3 \u5217 \xB7 0 errors"), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("span", {
    className: "t"
  }, "14:33:02"), " ", /*#__PURE__*/React.createElement("span", {
    className: "w"
  }, "[DRY]"), " \u82E5\u57F7\u884C LIVE \u5C07\u65B0\u589E 2\uFF0C\u8986\u84CB 1"))));
}
function ThresholdMatrix() {
  return /*#__PURE__*/React.createElement(Card, {
    title: "THRESHOLD EDITOR \xB7 iFIX3_SecondError",
    icon: /*#__PURE__*/React.createElement(Icon.shield, null),
    actions: /*#__PURE__*/React.createElement(Button, {
      variant: "primary",
      size: "sm",
      icon: /*#__PURE__*/React.createElement(Icon.check, null)
    }, "\u5132\u5B58")
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(3,1fr)',
      gap: 16
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("label", {
    style: fLab
  }, "Condition"), /*#__PURE__*/React.createElement("select", {
    className: "select",
    style: {
      width: '100%'
    }
  }, /*#__PURE__*/React.createElement("option", null, "less"), /*#__PURE__*/React.createElement("option", null, "greater"), /*#__PURE__*/React.createElement("option", null, "equal"), /*#__PURE__*/React.createElement("option", null, "not_equal"))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("label", {
    style: fLab
  }, "Threshold"), /*#__PURE__*/React.createElement("input", {
    className: "input",
    defaultValue: "60",
    style: {
      width: '100%'
    }
  })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("label", {
    style: fLab
  }, "CountNeeded (\u7D2F\u7A4D)"), /*#__PURE__*/React.createElement("input", {
    className: "input",
    defaultValue: "3",
    style: {
      width: '100%'
    }
  })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("label", {
    style: fLab
  }, "Device IP (L3)"), /*#__PURE__*/React.createElement("input", {
    className: "input",
    defaultValue: "10.0.1.20",
    style: {
      width: '100%'
    }
  })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("label", {
    style: fLab
  }, "Device Port"), /*#__PURE__*/React.createElement("input", {
    className: "input",
    defaultValue: "49310",
    style: {
      width: '100%'
    }
  })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("label", {
    style: fLab
  }, "Enable"), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 10
    }
  }, /*#__PURE__*/React.createElement(Pill, {
    kind: "ok"
  }, "ENABLED"))), /*#__PURE__*/React.createElement("div", {
    style: {
      gridColumn: '1 / -1'
    }
  }, /*#__PURE__*/React.createElement("label", {
    style: fLab
  }, "Mail to / cc"), /*#__PURE__*/React.createElement("input", {
    className: "input",
    defaultValue: "ops@factory.com; ops-lead@factory.com",
    style: {
      width: '100%'
    }
  }))));
}
const fLab = {
  display: 'block',
  fontSize: 10.5,
  color: '#94a3b8',
  textTransform: 'uppercase',
  letterSpacing: '0.08em',
  fontWeight: 600,
  marginBottom: 6
};

/* ---------------- ALERTS ---------------- */
function PageAlerts() {
  const [filter, setFilter] = useStateP('ALL');
  const filters = ['ALL', 'HOST_DOWN', 'OPC_SERVICE_DOWN', 'DEVICE_DOWN', 'IGS_SERVICE_DOWN', 'VALUE_ABNORMAL'];
  const rows = [['14:32:09', 'err', 'iFIX3_SecondError', 'VALUE_ABNORMAL', 'kepware_a', 'ops@factory.com', '派報'], ['14:28:41', 'err', 'kepware_a', 'HOST_DOWN', 'kepware_a', 'it@factory.com', '派報'], ['14:25:03', 'warn', 'iFIX7_SecondError', 'threshold 2/3', 'kepware_b', '—', '累積中'], ['13:52:18', 'err', 'Line3_StopFlag', 'VALUE_ABNORMAL', 'kepware_c', 'line3@factory.com', '派報'], ['13:20:04', 'ok', 'iFIX2_SecondError', 'RECOVERED', 'kepware_a', 'ops@factory.com', '復歸'], ['12:47:50', 'err', 'kepware_c', 'OPC_SERVICE_DOWN', 'kepware_c', 'it@factory.com', '派報']];
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "section-hd"
  }, /*#__PURE__*/React.createElement("h2", null, "\u544A\u8B66\u7D00\u9304"), /*#__PURE__*/React.createElement("span", {
    className: "count"
  }, "24h \xB7 14 events"), /*#__PURE__*/React.createElement("div", {
    className: "actions"
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "ghost",
    icon: /*#__PURE__*/React.createElement(Icon.download, null)
  }, "\u532F\u51FA CSV"))), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      gap: 6,
      flexWrap: 'wrap',
      marginBottom: 18
    }
  }, filters.map(f => /*#__PURE__*/React.createElement("div", {
    key: f,
    onClick: () => setFilter(f),
    style: {
      padding: '6px 14px',
      fontSize: 12,
      fontWeight: 600,
      color: f === filter ? '#03181c' : '#94a3b8',
      background: f === filter ? '#22d3ee' : 'transparent',
      border: `1px solid ${f === filter ? '#22d3ee' : '#293548'}`,
      borderRadius: 999,
      fontFamily: 'var(--font-mono)',
      letterSpacing: '0.04em',
      cursor: 'pointer'
    }
  }, f))), /*#__PURE__*/React.createElement(Card, null, /*#__PURE__*/React.createElement("div", {
    className: "tbl-wrap"
  }, /*#__PURE__*/React.createElement("table", null, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "Time"), /*#__PURE__*/React.createElement("th", null, "Subject"), /*#__PURE__*/React.createElement("th", null, "Category"), /*#__PURE__*/React.createElement("th", null, "Server"), /*#__PURE__*/React.createElement("th", null, "Routed to"), /*#__PURE__*/React.createElement("th", null, "State"))), /*#__PURE__*/React.createElement("tbody", null, rows.map((r, i) => /*#__PURE__*/React.createElement("tr", {
    key: i
  }, /*#__PURE__*/React.createElement("td", {
    className: "td-mono"
  }, r[0]), /*#__PURE__*/React.createElement("td", {
    style: {
      fontWeight: 600
    }
  }, /*#__PURE__*/React.createElement(Dot, {
    kind: r[1]
  }), r[2]), /*#__PURE__*/React.createElement("td", {
    className: "td-mono"
  }, r[3]), /*#__PURE__*/React.createElement("td", {
    className: "td-mono"
  }, r[4]), /*#__PURE__*/React.createElement("td", {
    className: "td-mono"
  }, r[5]), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Pill, {
    kind: r[1]
  }, r[6])))))))));
}

/* ---------------- DIAGNOSTICS TIMELINE ---------------- */
function PageDiag() {
  const steps = [{
    lvl: 'L1',
    ok: false,
    label: 'Ping Kepware Host',
    target: '192.168.1.10',
    msg: 'Ping 失敗 (timeout)',
    time: '14:32:09.120'
  }, {
    lvl: 'L1',
    ok: true,
    label: 'TCP OPC Port',
    target: '192.168.1.10:49320',
    msg: '— skipped (L1 fail)',
    time: '—'
  }, {
    lvl: 'L2',
    ok: null,
    label: 'OPC UA handshake',
    target: 'opc.tcp://192.168.1.10:49320',
    msg: '— skipped',
    time: '—'
  }, {
    lvl: 'L3',
    ok: false,
    label: 'Ping Device',
    target: '10.0.1.20',
    msg: 'Ping 失敗 (機台無法連線)',
    time: '14:32:09.180'
  }, {
    lvl: 'L3',
    ok: false,
    label: 'TCP IGS Port',
    target: '10.0.1.20:49310',
    msg: '— skipped (L3 ping fail)',
    time: '—'
  }];
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "banner err"
  }, /*#__PURE__*/React.createElement("div", {
    className: "banner-icon"
  }, /*#__PURE__*/React.createElement(Icon.alert, null)), /*#__PURE__*/React.createElement("div", {
    className: "banner-body"
  }, /*#__PURE__*/React.createElement("h4", null, "\u4E09\u5C64\u8A3A\u65B7 \xB7 iFIX3_SecondError \xB7 14:32:09"), /*#__PURE__*/React.createElement("p", null, "L1 HOST_DOWN + L3 DEVICE_DOWN \xB7 \u4E0A\u6E38\u4E3B\u6A5F\u8207\u4E0B\u6E38\u6A5F\u53F0\u540C\u6642\u7570\u5E38")), /*#__PURE__*/React.createElement(Button, {
    variant: "outline",
    size: "sm"
  }, "\u91CD\u8DD1\u8A3A\u65B7")), /*#__PURE__*/React.createElement("div", {
    className: "two-col",
    style: {
      gridTemplateColumns: '1.3fr 1fr'
    }
  }, /*#__PURE__*/React.createElement(Card, {
    title: "DIAGNOSTIC STEPS",
    icon: /*#__PURE__*/React.createElement(Icon.shield, null)
  }, steps.map((s, i) => {
    const kind = s.ok === true ? 'ok' : s.ok === false ? 'err' : 'muted';
    return /*#__PURE__*/React.createElement("div", {
      key: i,
      className: "diag"
    }, /*#__PURE__*/React.createElement("div", {
      className: `diag-icon ${kind}`
    }, s.ok === true ? /*#__PURE__*/React.createElement(Icon.check, null) : s.ok === false ? /*#__PURE__*/React.createElement(Icon.x, null) : /*#__PURE__*/React.createElement(Icon.clock, null)), /*#__PURE__*/React.createElement("div", {
      className: "diag-body"
    }, /*#__PURE__*/React.createElement("div", {
      className: "who"
    }, "[", s.lvl, "] ", s.label, " \xB7 ", /*#__PURE__*/React.createElement("span", {
      style: {
        color: '#94a3b8',
        fontWeight: 400
      }
    }, s.target)), /*#__PURE__*/React.createElement("div", {
      className: "msg"
    }, s.msg)), /*#__PURE__*/React.createElement("div", {
      className: "diag-time"
    }, s.time));
  }), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 14,
      padding: '12px 14px',
      background: 'var(--err-bg)',
      borderRadius: 8,
      border: '1px solid rgba(239,68,68,0.3)',
      fontSize: 13,
      color: '#fecaca'
    }
  }, /*#__PURE__*/React.createElement("strong", {
    style: {
      color: '#ef4444'
    }
  }, "\u7D50\u8AD6 \xB7 "), "Kepware \u4E3B\u6A5F 192.168.1.10 \u7121\u6CD5\u9023\u7DDA (Ping \u5931\u6557) \xB7 \u5DF2\u901A\u77E5 IT \u7FA4\u7D44 + ops@factory.com")), /*#__PURE__*/React.createElement(Card, {
    title: "EMAIL PREVIEW",
    icon: /*#__PURE__*/React.createElement(Icon.bell, null),
    actions: /*#__PURE__*/React.createElement(Button, {
      variant: "ghost",
      size: "sm"
    }, "\u6AA2\u8996\u539F\u59CB HTML")
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      background: 'var(--bg-0)',
      border: '1px solid var(--border-1)',
      borderRadius: 8,
      padding: 16,
      fontFamily: 'var(--font-mono)',
      fontSize: 12,
      color: '#cbd5e1',
      lineHeight: 1.8
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      color: '#64748b'
    }
  }, "Subject"), /*#__PURE__*/React.createElement("div", {
    style: {
      color: '#e6edf7',
      marginBottom: 10
    }
  }, "[\u7570\u5E38] Kepware \u8A2D\u5099\u76E3\u63A7\u901A\u77E5 - iFIX3_SecondError"), /*#__PURE__*/React.createElement("div", {
    style: {
      color: '#64748b'
    }
  }, "To"), /*#__PURE__*/React.createElement("div", {
    style: {
      color: '#e6edf7',
      marginBottom: 10
    }
  }, "ops@factory.com; ops-lead@factory.com"), /*#__PURE__*/React.createElement("div", {
    style: {
      color: '#64748b'
    }
  }, "Body"), /*#__PURE__*/React.createElement("div", {
    style: {
      color: '#fca5a5',
      marginTop: 4
    }
  }, "\u274C \u8A2D\u5099: iFIX3 (10.0.1.20)"), /*#__PURE__*/React.createElement("div", null, "\u8B80\u53D6\u5931\u6557\u6216\u9023\u7DDA\u65B7\u6389"), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 8
    }
  }, "\u8A3A\u65B7\u7D50\u679C:"), /*#__PURE__*/React.createElement("div", null, "\xB7 L1: \u4E3B\u6A5F 192.168.1.10 \u7121\u6CD5\u9023\u7DDA (Ping \u5931\u6557)"), /*#__PURE__*/React.createElement("div", null, "\xB7 L3: iFIX/IGS \u6A5F\u53F0 10.0.1.20 \u7121\u6CD5\u9023\u7DDA"), /*#__PURE__*/React.createElement("div", {
    style: {
      marginTop: 8,
      color: '#94a3b8'
    }
  }, "\u6642\u9593: 2026-04-19 14:32:09")))));
}

/* ---------------- HISTORY ---------------- */
function PageHistory() {
  return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
    className: "section-hd"
  }, /*#__PURE__*/React.createElement("h2", null, "\u6B77\u53F2\u8CC7\u6599\u67E5\u8A62"), /*#__PURE__*/React.createElement("span", {
    className: "count"
  }, "monitor_history \xB7 2.4M rows"), /*#__PURE__*/React.createElement("div", {
    className: "actions"
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "outline",
    icon: /*#__PURE__*/React.createElement(Icon.download, null)
  }, "\u532F\u51FA CSV"))), /*#__PURE__*/React.createElement(Card, null, /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'grid',
      gridTemplateColumns: '1fr 1fr 1fr 1fr auto',
      gap: 12,
      marginBottom: 16
    }
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("label", {
    style: fLab
  }, "Server"), /*#__PURE__*/React.createElement("select", {
    className: "select",
    style: {
      width: '100%'
    }
  }, /*#__PURE__*/React.createElement("option", null, "\u5168\u90E8"), /*#__PURE__*/React.createElement("option", null, "kepware_a"))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("label", {
    style: fLab
  }, "Tag"), /*#__PURE__*/React.createElement("select", {
    className: "select",
    style: {
      width: '100%'
    }
  }, /*#__PURE__*/React.createElement("option", null, "iFIX3_SecondError"))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("label", {
    style: fLab
  }, "From"), /*#__PURE__*/React.createElement("input", {
    className: "input",
    defaultValue: "2026-04-19 00:00",
    style: {
      width: '100%'
    }
  })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("label", {
    style: fLab
  }, "To"), /*#__PURE__*/React.createElement("input", {
    className: "input",
    defaultValue: "2026-04-19 23:59",
    style: {
      width: '100%'
    }
  })), /*#__PURE__*/React.createElement("div", {
    style: {
      display: 'flex',
      alignItems: 'flex-end'
    }
  }, /*#__PURE__*/React.createElement(Button, {
    variant: "primary",
    icon: /*#__PURE__*/React.createElement(Icon.search, null)
  }, "\u67E5\u8A62"))), /*#__PURE__*/React.createElement("div", {
    style: {
      height: 180,
      background: 'linear-gradient(180deg, rgba(34,211,238,0.04) 0%, transparent 100%)',
      border: '1px solid var(--border-1)',
      borderRadius: 8,
      padding: '14px 18px',
      position: 'relative',
      marginBottom: 16
    }
  }, /*#__PURE__*/React.createElement("div", {
    style: {
      fontSize: 10.5,
      color: '#64748b',
      textTransform: 'uppercase',
      letterSpacing: '0.08em',
      fontWeight: 600
    }
  }, "iFIX3_SecondError \xB7 last 24h"), /*#__PURE__*/React.createElement("svg", {
    viewBox: "0 0 800 120",
    preserveAspectRatio: "none",
    style: {
      width: '100%',
      height: 140,
      marginTop: 4
    }
  }, /*#__PURE__*/React.createElement("defs", null, /*#__PURE__*/React.createElement("linearGradient", {
    id: "gArea",
    x1: "0",
    x2: "0",
    y1: "0",
    y2: "1"
  }, /*#__PURE__*/React.createElement("stop", {
    offset: "0",
    stopColor: "#22d3ee",
    stopOpacity: "0.4"
  }), /*#__PURE__*/React.createElement("stop", {
    offset: "1",
    stopColor: "#22d3ee",
    stopOpacity: "0"
  }))), [...Array(9)].map((_, i) => /*#__PURE__*/React.createElement("line", {
    key: i,
    x1: i * 100,
    y1: "0",
    x2: i * 100,
    y2: "120",
    stroke: "rgba(96,165,250,0.08)"
  })), /*#__PURE__*/React.createElement("line", {
    x1: "0",
    y1: "40",
    x2: "800",
    y2: "40",
    stroke: "#f59e0b",
    strokeDasharray: "4 6",
    strokeOpacity: "0.5"
  }), /*#__PURE__*/React.createElement("text", {
    x: "6",
    y: "36",
    fill: "#f59e0b",
    fontSize: "9",
    fontFamily: "monospace"
  }, "THR 60"), /*#__PURE__*/React.createElement("path", {
    d: "M0,80 L50,75 L100,72 L150,78 L200,65 L250,50 L300,55 L350,48 L400,44 L420,30 L440,20 L460,15 L480,18 L520,22 L560,28 L600,35 L640,46 L680,54 L720,62 L760,70 L800,72 L800,120 L0,120 Z",
    fill: "url(#gArea)"
  }), /*#__PURE__*/React.createElement("path", {
    d: "M0,80 L50,75 L100,72 L150,78 L200,65 L250,50 L300,55 L350,48 L400,44 L420,30 L440,20 L460,15 L480,18 L520,22 L560,28 L600,35 L640,46 L680,54 L720,62 L760,70 L800,72",
    fill: "none",
    stroke: "#22d3ee",
    strokeWidth: "1.5"
  }), /*#__PURE__*/React.createElement("circle", {
    cx: "460",
    cy: "15",
    r: "4",
    fill: "#ef4444",
    stroke: "#0f172a",
    strokeWidth: "2"
  }))), /*#__PURE__*/React.createElement("div", {
    className: "tbl-wrap"
  }, /*#__PURE__*/React.createElement("table", null, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "Timestamp"), /*#__PURE__*/React.createElement("th", null, "Tag"), /*#__PURE__*/React.createElement("th", {
    className: "td-num"
  }, "Value"), /*#__PURE__*/React.createElement("th", null, "Condition met"), /*#__PURE__*/React.createElement("th", null, "Event"))), /*#__PURE__*/React.createElement("tbody", null, [['2026-04-19 14:32:09', 'iFIX3_SecondError', '124', 'true', 'ALERT'], ['2026-04-19 14:31:09', 'iFIX3_SecondError', '78', 'true', '—'], ['2026-04-19 14:30:09', 'iFIX3_SecondError', '62', 'true', '—'], ['2026-04-19 14:29:09', 'iFIX3_SecondError', '45', 'false', 'RECOVER'], ['2026-04-19 14:28:09', 'iFIX3_SecondError', '12', 'false', '—']].map((r, i) => /*#__PURE__*/React.createElement("tr", {
    key: i
  }, /*#__PURE__*/React.createElement("td", {
    className: "td-mono"
  }, r[0]), /*#__PURE__*/React.createElement("td", {
    style: {
      fontWeight: 600
    }
  }, r[1]), /*#__PURE__*/React.createElement("td", {
    className: "td-num",
    style: {
      color: +r[2] > 60 ? '#ef4444' : '#e6edf7'
    }
  }, r[2]), /*#__PURE__*/React.createElement("td", {
    className: "td-mono"
  }, /*#__PURE__*/React.createElement(Pill, {
    kind: r[3] === 'true' ? 'err' : 'ok'
  }, r[3])), /*#__PURE__*/React.createElement("td", {
    className: "td-mono"
  }, r[4] === 'ALERT' ? /*#__PURE__*/React.createElement(Pill, {
    kind: "err"
  }, "ALERT") : r[4] === 'RECOVER' ? /*#__PURE__*/React.createElement(Pill, {
    kind: "ok"
  }, "RECOVER") : '—'))))))));
}
Object.assign(window, {
  PageChannels,
  PageTags,
  PageAlerts,
  PageDiag,
  PageHistory
});
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/dashboard/pages.jsx", error: String((e && e.message) || e) }); }

})();
