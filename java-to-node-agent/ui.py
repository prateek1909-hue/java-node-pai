"""
Java-to-Node Agent — File Selection UI
Run:  python ui.py
Then open  http://localhost:5050  in your browser.
"""

import json
import os
import queue
import sys
import threading
from pathlib import Path

from flask import Flask, Response, jsonify, render_template_string, request, stream_with_context

# Make sure the project root is importable
sys.path.insert(0, str(Path(__file__).parent))

from src.config.settings import get_settings
from src.analyzers.code_scanner import CodeScanner
from src.analyzers.dependency_mapper import DependencyMapper
from src.graph.workflow import create_conversion_workflow
from src.graph.state import create_initial_state

app = Flask(__name__)

# ---------------------------------------------------------------------------
# HTML / CSS / JS  (single-file, no external template directory)
# ---------------------------------------------------------------------------

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Java → Node Converter</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=JetBrains+Mono:wght@400;500&display=swap');

  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:           #060810;
    --bg-grid:      #060810;
    --surface:      rgba(255,255,255,.032);
    --surface-b:    rgba(255,255,255,.055);
    --surface-c:    rgba(255,255,255,.08);
    --border:       rgba(255,255,255,.08);
    --border-hi:    rgba(255,255,255,.14);
    --text-1:       #f0f4ff;
    --text-2:       #8892a4;
    --text-3:       #4a5263;
    --accent:       #4f8fff;
    --accent-glow:  rgba(79,143,255,.35);
    --green:        #34d399;
    --green-glow:   rgba(52,211,153,.3);
    --amber:        #f59e0b;
    --red:          #f87171;
    --ctrl-color:   #60a5fa;
    --ctrl-glow:    rgba(96,165,250,.18);
    --svc-color:    #34d399;
    --svc-glow:     rgba(52,211,153,.18);
    --dao-color:    #fbbf24;
    --dao-glow:     rgba(251,191,36,.18);
    --radius-lg:    14px;
    --radius-md:    10px;
    --radius-sm:    7px;
  }

  html { font-size: 15px; }

  body {
    font-family: 'Inter', system-ui, sans-serif;
    background: var(--bg);
    color: var(--text-1);
    min-height: 100vh;
    line-height: 1.55;
    /* subtle dot-grid background */
    background-image: radial-gradient(rgba(255,255,255,.035) 1px, transparent 1px);
    background-size: 28px 28px;
  }

  /* ── scrollbar ── */
  ::-webkit-scrollbar { width: 5px; height: 5px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: rgba(255,255,255,.1); border-radius: 99px; }
  ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,.18); }

  /* ── layout ── */
  .page { max-width: 1300px; margin: 0 auto; padding: 36px 24px 64px; }

  /* ── glass card mixin ── */
  .glass {
    background: var(--surface);
    border: 1px solid var(--border);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
  }

  /* ══════════════════════════════════════════
     HERO
  ══════════════════════════════════════════ */
  .hero {
    position: relative; overflow: hidden;
    border-radius: var(--radius-lg);
    border: 1px solid var(--border-hi);
    background: linear-gradient(145deg, #0b0f1e 0%, #08091a 55%, #0f0818 100%);
    padding: 32px 36px 28px;
    margin-bottom: 16px;
    box-shadow: 0 0 0 1px rgba(255,255,255,.04), 0 24px 64px rgba(0,0,0,.6);
  }

  /* animated aurora glows */
  .hero::before, .hero::after {
    content: ''; position: absolute; border-radius: 50%; pointer-events: none;
    filter: blur(60px); opacity: .55;
  }
  .hero::before {
    width: 480px; height: 320px; top: -120px; left: -60px;
    background: radial-gradient(ellipse, rgba(79,143,255,.22), transparent 70%);
    animation: drift1 12s ease-in-out infinite alternate;
  }
  .hero::after {
    width: 360px; height: 260px; bottom: -100px; right: -40px;
    background: radial-gradient(ellipse, rgba(139,92,246,.18), transparent 70%);
    animation: drift2 15s ease-in-out infinite alternate;
  }
  @keyframes drift1 { from { transform: translate(0,0) scale(1); } to { transform: translate(30px,20px) scale(1.08); } }
  @keyframes drift2 { from { transform: translate(0,0) scale(1); } to { transform: translate(-20px,-15px) scale(1.1); } }

  /* thin shimmer line at top */
  .hero-shimmer {
    position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent 0%, rgba(120,160,255,.6) 40%, rgba(180,120,255,.5) 60%, transparent 100%);
  }

  .hero-inner { position: relative; z-index: 1; }

  .hero-top { display: flex; align-items: center; gap: 18px; margin-bottom: 28px; }

  .hero-logo {
    width: 52px; height: 52px; border-radius: 14px; flex-shrink: 0;
    background: linear-gradient(145deg, #1a2f5e, #261656);
    border: 1px solid rgba(100,150,255,.3);
    display: flex; align-items: center; justify-content: center;
    font-size: 24px;
    box-shadow: 0 0 20px rgba(79,143,255,.25), inset 0 1px 0 rgba(255,255,255,.12);
  }

  .hero-text { flex: 1; }
  .hero-title {
    font-size: 1.45rem; font-weight: 700; letter-spacing: -.03em;
    background: linear-gradient(120deg, #c8d8ff 20%, #a78bfa 80%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  .hero-sub { font-size: .82rem; color: var(--text-2); margin-top: 4px; font-weight: 400; }

  .hero-badge {
    flex-shrink: 0;
    font-size: .68rem; font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
    padding: 4px 12px; border-radius: 999px;
    background: linear-gradient(135deg, rgba(79,143,255,.15), rgba(139,92,246,.15));
    color: #a5b8ff;
    border: 1px solid rgba(120,160,255,.25);
    box-shadow: 0 0 12px rgba(79,143,255,.15);
  }

  /* ── form fields ── */
  .fields { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px; }
  @media (max-width: 680px) { .fields { grid-template-columns: 1fr; } }

  .field-group { display: flex; flex-direction: column; gap: 7px; }
  .field-group label {
    font-size: .7rem; font-weight: 600; letter-spacing: .07em; text-transform: uppercase;
    color: var(--text-3);
  }

  .input-wrap { position: relative; }
  .input-icon {
    position: absolute; left: 12px; top: 50%; transform: translateY(-50%);
    font-size: .85rem; color: var(--text-3); pointer-events: none;
  }
  .field-group input[type=text] {
    width: 100%;
    padding: 10px 14px 10px 34px;
    background: rgba(255,255,255,.04);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm);
    color: var(--text-1);
    font-family: 'JetBrains Mono', Consolas, monospace;
    font-size: .8rem;
    outline: none;
    transition: border-color .18s, box-shadow .18s, background .18s;
  }
  .field-group input[type=text]:hover { background: rgba(255,255,255,.06); border-color: var(--border-hi); }
  .field-group input[type=text]:focus {
    background: rgba(79,143,255,.06);
    border-color: rgba(79,143,255,.5);
    box-shadow: 0 0 0 3px rgba(79,143,255,.12);
  }
  .field-group input[type=text]::placeholder { color: var(--text-3); }

  /* ── action bar ── */
  .action-bar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }

  /* ── buttons ── */
  button {
    cursor: pointer; border: none;
    border-radius: var(--radius-sm);
    padding: 10px 20px; font-size: .83rem; font-weight: 600;
    font-family: 'Inter', system-ui, sans-serif;
    display: inline-flex; align-items: center; gap: 8px;
    transition: all .16s ease;
    white-space: nowrap; position: relative; overflow: hidden;
  }
  button::after {
    content: ''; position: absolute; inset: 0;
    background: rgba(255,255,255,0);
    transition: background .16s;
    border-radius: inherit;
  }
  button:not(:disabled):hover::after { background: rgba(255,255,255,.06); }
  button:not(:disabled):active { transform: scale(.967); }
  button:disabled { opacity: .35; cursor: not-allowed; }

  .btn-primary {
    background: linear-gradient(135deg, #1a3f8f 0%, #2f6be8 100%);
    color: #fff;
    border: 1px solid rgba(100,160,255,.3);
    box-shadow: 0 1px 0 rgba(255,255,255,.1) inset,
                0 4px 16px rgba(47,107,232,.35),
                0 0 0 1px rgba(47,107,232,.2);
  }
  .btn-primary:not(:disabled):hover {
    box-shadow: 0 1px 0 rgba(255,255,255,.1) inset,
                0 6px 24px rgba(47,107,232,.5),
                0 0 0 1px rgba(47,107,232,.3);
  }

  .btn-success {
    background: linear-gradient(135deg, #0d4a2e 0%, #16a34a 100%);
    color: #fff;
    border: 1px solid rgba(52,211,153,.25);
    box-shadow: 0 1px 0 rgba(255,255,255,.08) inset,
                0 4px 16px rgba(22,163,74,.3),
                0 0 0 1px rgba(22,163,74,.15);
  }
  .btn-success:not(:disabled):hover {
    box-shadow: 0 1px 0 rgba(255,255,255,.08) inset,
                0 6px 24px rgba(52,211,153,.4),
                0 0 0 1px rgba(52,211,153,.25);
  }

  .btn-ghost {
    background: rgba(255,255,255,.04);
    border: 1px solid var(--border);
    color: var(--text-2);
  }
  .btn-ghost:not(:disabled):hover { border-color: var(--border-hi); color: var(--text-1); }

  .btn-sm { padding: 5px 11px; font-size: .74rem; border-radius: 6px; }

  /* ── status bar ── */
  #statusBar {
    font-size: .79rem; margin-top: 16px;
    padding: 9px 14px; border-radius: var(--radius-sm);
    display: flex; align-items: center; gap: 8px;
    transition: all .2s;
  }
  #statusBar:empty { display: none; }
  .status-muted   { background: rgba(255,255,255,.04); color: var(--text-2); border: 1px solid var(--border); }
  .status-success { background: rgba(52,211,153,.07);  color: #34d399; border: 1px solid rgba(52,211,153,.2); }
  .status-danger  { background: rgba(248,113,113,.07); color: #f87171; border: 1px solid rgba(248,113,113,.2); }
  .status-warning { background: rgba(245,158,11,.07);  color: #f59e0b; border: 1px solid rgba(245,158,11,.2); }

  .sel-pill {
    margin-left: auto; flex-shrink: 0;
    font-size: .71rem; font-weight: 600; padding: 3px 10px; border-radius: 999px;
    background: linear-gradient(135deg, rgba(79,143,255,.15), rgba(139,92,246,.12));
    color: #a5b8ff; border: 1px solid rgba(100,150,255,.2);
  }

  /* ══════════════════════════════════════════
     DEPENDENCY TOOLBAR
  ══════════════════════════════════════════ */
  .dep-toolbar {
    display: none;
    align-items: center; gap: 14px; flex-wrap: wrap;
    background: rgba(255,255,255,.025);
    border: 1px solid var(--border);
    border-radius: var(--radius-md);
    padding: 11px 18px;
    margin-bottom: 18px;
    font-size: .8rem;
    backdrop-filter: blur(8px);
  }
  .dep-toolbar.visible { display: flex; }

  .dep-divider { width: 1px; height: 20px; background: var(--border); flex-shrink: 0; }

  .dep-label {
    font-size: .7rem; font-weight: 600; letter-spacing: .06em; text-transform: uppercase;
    color: var(--text-3); display: flex; align-items: center; gap: 6px;
  }
  .dep-label-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 6px var(--accent); }

  .toggle-wrap { display: flex; align-items: center; gap: 9px; cursor: pointer; user-select: none; }
  .toggle-wrap input[type=checkbox] { display: none; }
  .toggle-track {
    width: 36px; height: 20px; border-radius: 999px;
    background: rgba(255,255,255,.1); border: 1px solid var(--border);
    position: relative; transition: background .2s, border-color .2s; flex-shrink: 0;
  }
  .toggle-wrap input:checked + .toggle-track {
    background: linear-gradient(135deg, #1a3f8f, #2f6be8);
    border-color: rgba(79,143,255,.4);
    box-shadow: 0 0 10px rgba(79,143,255,.3);
  }
  .toggle-track::after {
    content: ''; position: absolute; top: 2px; left: 2px;
    width: 14px; height: 14px; border-radius: 50%;
    background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.3);
    transition: left .2s cubic-bezier(.34,1.56,.64,1);
  }
  .toggle-wrap input:checked + .toggle-track::after { left: 18px; }
  .toggle-label { color: var(--text-1); font-weight: 500; font-size: .8rem; }

  .dep-stats { margin-left: auto; font-size: .73rem; color: var(--text-3); font-family: 'JetBrains Mono', monospace; }

  /* ══════════════════════════════════════════
     SECTION LABEL
  ══════════════════════════════════════════ */
  .section-label {
    font-size: .68rem; font-weight: 600; letter-spacing: .09em; text-transform: uppercase;
    color: var(--text-3); margin-bottom: 14px;
    display: flex; align-items: center; gap: 10px;
  }
  .section-label::after {
    content: ''; flex: 1; height: 1px; background: var(--border);
  }

  /* ══════════════════════════════════════════
     FILE GRIDS
  ══════════════════════════════════════════ */
  .grids { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
  @media (max-width: 920px) { .grids { grid-template-columns: 1fr; } }

  .grid-card {
    border-radius: var(--radius-lg);
    border: 1px solid var(--border);
    background: linear-gradient(160deg, rgba(255,255,255,.035) 0%, rgba(255,255,255,.018) 100%);
    display: flex; flex-direction: column;
    overflow: hidden;
    box-shadow: 0 1px 0 rgba(255,255,255,.04) inset, 0 8px 32px rgba(0,0,0,.4);
    transition: border-color .2s, box-shadow .2s, transform .2s;
  }
  .grid-card:hover {
    border-color: var(--border-hi);
    box-shadow: 0 1px 0 rgba(255,255,255,.06) inset, 0 12px 40px rgba(0,0,0,.5);
    transform: translateY(-1px);
  }

  /* coloured top accent bar */
  .grid-card-ctrl { border-top: 2px solid transparent; border-image: linear-gradient(90deg, #3b82f6, #818cf8) 1; }
  .grid-card-svc  { border-top: 2px solid transparent; border-image: linear-gradient(90deg, #10b981, #34d399) 1; }
  .grid-card-dao  { border-top: 2px solid transparent; border-image: linear-gradient(90deg, #f59e0b, #fcd34d) 1; }

  .grid-head {
    display: flex; align-items: center; gap: 10px;
    padding: 14px 18px 12px;
    border-bottom: 1px solid var(--border);
    font-weight: 600; font-size: .88rem;
  }
  .head-controller { color: var(--ctrl-color); }
  .head-service    { color: var(--svc-color);  }
  .head-dao        { color: var(--dao-color);  }

  .head-icon {
    width: 28px; height: 28px; border-radius: 8px;
    display: flex; align-items: center; justify-content: center;
    font-size: .95rem; flex-shrink: 0;
  }
  .head-controller .head-icon { background: var(--ctrl-glow); }
  .head-service    .head-icon { background: var(--svc-glow);  }
  .head-dao        .head-icon { background: var(--dao-glow);  }

  .badge {
    font-size: .66rem; font-weight: 700; padding: 2px 8px;
    border-radius: 999px; margin-left: auto;
  }
  .head-controller .badge { background: rgba(96,165,250,.15); color: var(--ctrl-color); border: 1px solid rgba(96,165,250,.2); }
  .head-service    .badge { background: rgba(52,211,153,.15);  color: var(--svc-color);  border: 1px solid rgba(52,211,153,.2);  }
  .head-dao        .badge { background: rgba(251,191,36,.15);  color: var(--dao-color);  border: 1px solid rgba(251,191,36,.2);  }

  .file-list { flex: 1; overflow-y: auto; max-height: 360px; padding: 8px; }

  .file-item {
    display: flex; align-items: flex-start; gap: 10px;
    padding: 8px 10px; border-radius: var(--radius-sm);
    transition: background .12s;
    border: 1px solid transparent;
  }
  .file-item:hover { background: rgba(255,255,255,.04); border-color: var(--border); }
  .file-item.is-checked {
    background: rgba(79,143,255,.07);
    border-color: rgba(79,143,255,.18);
  }
  .file-item.is-auto-dep {
    background: rgba(79,143,255,.04);
    border-color: rgba(79,143,255,.12);
    border-left: 2px solid rgba(79,143,255,.4);
  }
  .file-item.is-auto-dep .class-name { color: #93b8ff; }

  .file-item input[type=checkbox] {
    margin-top: 3px; width: 15px; height: 15px; flex-shrink: 0;
    accent-color: var(--accent); cursor: pointer;
  }
  .file-label { cursor: pointer; line-height: 1.4; word-break: break-all; flex: 1; min-width: 0; }
  .class-name { font-weight: 600; font-size: .83rem; display: block; color: var(--text-1); }
  .pkg-name   { font-size: .7rem; color: var(--text-3); font-family: 'JetBrains Mono', monospace; }

  .empty-note {
    color: var(--text-3); font-size: .81rem;
    padding: 36px 16px; text-align: center;
    display: flex; flex-direction: column; align-items: center; gap: 10px;
  }
  .empty-icon { font-size: 2rem; opacity: .25; }

  .grid-foot {
    display: flex; align-items: center; gap: 8px;
    padding: 10px 14px; border-top: 1px solid var(--border);
    background: rgba(0,0,0,.2);
  }
  .sel-count { margin-left: auto; font-size: .73rem; color: var(--text-3); font-family: 'JetBrains Mono', monospace; }

  /* dep badges */
  .dep-tag {
    display: inline-flex; align-items: center; gap: 3px;
    font-size: .63rem; font-weight: 600; padding: 1px 6px;
    border-radius: 4px; margin-left: 5px; vertical-align: middle;
    background: rgba(79,143,255,.12); color: #7baeff;
    border: 1px solid rgba(79,143,255,.2);
    letter-spacing: .03em;
  }
  .dep-count-badge {
    display: inline-flex; align-items: center; gap: 2px;
    font-size: .63rem; padding: 1px 6px; border-radius: 4px;
    background: rgba(245,158,11,.1); color: #fbbf24;
    border: 1px solid rgba(245,158,11,.18);
    margin-left: 5px; vertical-align: middle; cursor: help;
  }

  /* ══════════════════════════════════════════
     LOG PANEL
  ══════════════════════════════════════════ */
  #logSection { margin-top: 20px; display: none; }

  .log-card {
    border-radius: var(--radius-lg);
    border: 1px solid var(--border);
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(0,0,0,.5);
  }
  .log-title-bar {
    display: flex; justify-content: space-between; align-items: center;
    padding: 12px 18px;
    border-bottom: 1px solid var(--border);
    background: rgba(255,255,255,.03);
  }
  .log-title {
    font-size: .75rem; font-weight: 600; color: var(--text-2);
    display: flex; align-items: center; gap: 8px;
    letter-spacing: .07em; text-transform: uppercase;
  }
  /* macOS-style traffic lights */
  .log-dots { display: flex; gap: 6px; align-items: center; }
  .log-dot-r { width: 10px; height: 10px; border-radius: 50%; background: #ff5f57; }
  .log-dot-y { width: 10px; height: 10px; border-radius: 50%; background: #febc2e; }
  .log-dot-g {
    width: 10px; height: 10px; border-radius: 50%; background: #28c840;
    box-shadow: 0 0 6px rgba(40,200,64,.6);
    animation: pulse-g 2s ease-in-out infinite;
  }
  @keyframes pulse-g { 0%,100% { box-shadow: 0 0 6px rgba(40,200,64,.6); } 50% { box-shadow: 0 0 12px rgba(40,200,64,.9); } }

  #logPanel {
    background: #020508;
    color: #c9d1d9;
    padding: 16px 20px;
    font-family: 'JetBrains Mono', Consolas, monospace; font-size: .77rem;
    line-height: 1.75; max-height: 420px; overflow-y: auto; white-space: pre-wrap;
  }
  .log-line { display: flex; gap: 12px; align-items: flex-start; padding: 1px 0; }
  .log-ts   { color: #2d3748; flex-shrink: 0; user-select: none; font-size: .7rem; padding-top: .15em; min-width: 56px; }
  .log-msg  { flex: 1; }
  .log-info  .log-msg { color: #7bb3f7; }
  .log-warn  .log-msg { color: #f59e0b; }
  .log-error .log-msg { color: #f87171; }
  .log-ok    .log-msg { color: #34d399; }
  .log-ok    .log-ts  { color: rgba(52,211,153,.3); }

  /* ── spinner ── */
  .spin {
    display: inline-block; width: 13px; height: 13px;
    border: 2px solid rgba(255,255,255,.2);
    border-top-color: rgba(255,255,255,.85);
    border-radius: 50%; animation: spin .6s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .4; } }
  .hidden { display: none !important; }
</style>
</head>
<body>
<div class="page">

  <!-- ══ HERO ══ -->
  <div class="hero">
    <div class="hero-shimmer"></div>
    <div class="hero-inner">

      <div class="hero-top">
        <div class="hero-logo">&#9749;</div>
        <div class="hero-text">
          <div class="hero-title">Java &rarr; Node.js Converter</div>
          <div class="hero-sub">Scan a Spring codebase, select files, and convert to Node.js microservices</div>
        </div>
        <div class="hero-badge">AI-Powered</div>
      </div>

      <!-- Inputs -->
      <div class="fields">
        <div class="field-group">
          <label for="dirInput">Java Source Directory</label>
          <div class="input-wrap">
            <span class="input-icon">&#128193;</span>
            <input id="dirInput" type="text" placeholder="C:\\projects\\my-app\\src\\main\\java" />
          </div>
        </div>
        <div class="field-group">
          <label for="outDirInput">Output Directory</label>
          <div class="input-wrap">
            <span class="input-icon">&#128228;</span>
            <input id="outDirInput" type="text" value="outputs/interactive_selected" />
          </div>
        </div>
      </div>

      <!-- Actions -->
      <div class="action-bar">
        <button id="scanBtn" class="btn-primary" onclick="doScan()">
          <span id="scanSpin" class="spin hidden"></span>
          <span>&#128270; Scan</span>
        </button>
        <button id="convertBtn" class="btn-success" disabled onclick="doConvert()">
          <span id="convertSpin" class="spin hidden"></span>
          <span>&#9889; Convert to Node.js</span>
        </button>
        <span id="selSummary" class="sel-pill" style="display:none"></span>
      </div>

      <div id="statusBar"></div>
    </div>
  </div>

  <!-- ══ DEPENDENCY TOOLBAR ══ -->
  <div class="dep-toolbar" id="depToolbar">
    <div class="dep-label"><span class="dep-label-dot"></span>Dependencies</div>
    <div class="dep-divider"></div>
    <label class="toggle-wrap" title="When ON, selecting a class automatically selects all classes it depends on (transitive)">
      <input type="checkbox" id="autoDepsToggle" checked onchange="onAutoDepsToggle()" />
      <span class="toggle-track"></span>
      <span class="toggle-label">Auto-include dependencies</span>
    </label>
    <div class="dep-divider"></div>
    <button class="btn-ghost btn-sm" onclick="expandAllDeps()" title="Resolve & select dependencies for all currently checked files">Expand deps</button>
    <button class="btn-ghost btn-sm" onclick="clearAutoDeps()" title="Uncheck auto-selected deps (manual selections stay)">Clear auto-deps</button>
    <span class="dep-stats" id="depStats"></span>
  </div>

  <!-- ══ FILE GRIDS ══ -->
  <div class="section-label">Discovered Files</div>
  <div class="grids">

    <!-- Controllers -->
    <div class="grid-card grid-card-ctrl">
      <div class="grid-head head-controller">
        <div class="head-icon">&#127758;</div>
        Controllers
        <span class="badge" id="cCount">0</span>
      </div>
      <div class="file-list" id="cGrid">
        <div class="empty-note"><span class="empty-icon">&#128196;</span>Scan a directory to see files</div>
      </div>
      <div class="grid-foot">
        <button class="btn-ghost btn-sm" onclick="selAll('Controller')">All</button>
        <button class="btn-ghost btn-sm" onclick="selNone('Controller')">None</button>
        <span class="sel-count" id="cSel">0 selected</span>
      </div>
    </div>

    <!-- Services -->
    <div class="grid-card grid-card-svc">
      <div class="grid-head head-service">
        <div class="head-icon">&#9881;</div>
        Services
        <span class="badge" id="sCount">0</span>
      </div>
      <div class="file-list" id="sGrid">
        <div class="empty-note"><span class="empty-icon">&#128196;</span>Scan a directory to see files</div>
      </div>
      <div class="grid-foot">
        <button class="btn-ghost btn-sm" onclick="selAll('Service')">All</button>
        <button class="btn-ghost btn-sm" onclick="selNone('Service')">None</button>
        <span class="sel-count" id="sSel">0 selected</span>
      </div>
    </div>

    <!-- DAOs -->
    <div class="grid-card grid-card-dao">
      <div class="grid-head head-dao">
        <div class="head-icon">&#128451;</div>
        DAOs / Repositories
        <span class="badge" id="dCount">0</span>
      </div>
      <div class="file-list" id="dGrid">
        <div class="empty-note"><span class="empty-icon">&#128196;</span>Scan a directory to see files</div>
      </div>
      <div class="grid-foot">
        <button class="btn-ghost btn-sm" onclick="selAll('DAO')">All</button>
        <button class="btn-ghost btn-sm" onclick="selNone('DAO')">None</button>
        <span class="sel-count" id="dSel">0 selected</span>
      </div>
    </div>
  </div>

  <!-- ══ CONVERSION LOG ══ -->
  <div id="logSection">
    <div class="log-card" style="margin-top:20px">
      <div class="log-title-bar">
        <div class="log-dots">
          <div class="log-dot-r"></div>
          <div class="log-dot-y"></div>
          <div class="log-dot-g"></div>
        </div>
        <div class="log-title" style="margin-left:12px">Conversion Log</div>
        <button class="btn-ghost btn-sm" style="margin-left:auto" onclick="document.getElementById('logPanel').innerHTML=''">Clear</button>
      </div>
      <div id="logPanel"></div>
    </div>
  </div>

</div><!-- /page -->
<script>
'use strict';
// ── state ──────────────────────────────────────────────────────────
let allFiles   = [];     // [{path, category, class_name, package_name}, ...]
let depGraph   = {};     // {ClassName: [DepClassName, ...]}  (direct deps, project-only)
let nameToPath = {};     // {ClassName -> path}
let pathToName = {};     // {path -> ClassName}
let manualSel  = new Set();   // paths explicitly checked by the user
let autoDepSel = new Set();   // paths pulled in automatically by dep resolution

// ── scan ───────────────────────────────────────────────────────────
async function doScan() {
  const dir = document.getElementById('dirInput').value.trim();
  if (!dir) { status('Please enter a directory path.', 'danger'); return; }

  setScanBusy(true);
  status('Scanning and indexing dependencies\u2026', 'muted');

  try {
    const r = await fetch('/scan', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ directory: dir })
    });
    const d = await r.json();
    if (!r.ok) { status('Error: ' + (d.error || r.statusText), 'danger'); return; }

    allFiles   = d.files;
    depGraph   = d.dep_graph || {};
    manualSel  = new Set();
    autoDepSel = new Set();

    // Build lookup maps
    nameToPath = {};
    pathToName = {};
    allFiles.forEach(f => {
      if (f.class_name) {
        nameToPath[f.class_name] = f.path;
        pathToName[f.path]       = f.class_name;
      }
    });

    renderAll();
    document.getElementById('depToolbar').classList.add('visible');

    const nc = cnt('Controller'), ns = cnt('Service'), nd = cnt('DAO');
    const depCount = Object.keys(depGraph).length;
    status(
      'Found ' + allFiles.length + ' files: ' + nc + ' controller(s), ' +
      ns + ' service(s), ' + nd + ' DAO(s). ' +
      depCount + ' class(es) have tracked dependencies.',
      'muted'
    );
    updateDepStats();
  } catch(e) {
    status('Network error: ' + e.message, 'danger');
  } finally {
    setScanBusy(false);
  }
}

// ── render grids ───────────────────────────────────────────────────
function renderAll() {
  renderGrid('Controller', 'cGrid', 'cCount');
  renderGrid('Service',    'sGrid', 'sCount');
  renderGrid('DAO',        'dGrid', 'dCount');
  refreshCounts();
}

function renderGrid(cat, gridId, countId) {
  const files = allFiles.filter(f => f.category === cat);
  document.getElementById(countId).textContent = files.length;
  const el = document.getElementById(gridId);
  if (!files.length) {
    el.innerHTML = '<div class="empty-note"><span class="empty-icon">&#128196;</span>No ' + cat + ' files found</div>';
    return;
  }

  el.innerHTML = files.map((f, i) => {
    const id   = 'cb_' + cat + '_' + i;
    const cls  = f.class_name || f.path.split('/').pop().replace('.java','');
    const pkg  = f.package_name || '';
    const deps = depGraph[cls] || [];
    // Only count deps that are in our visible file list
    const knownDeps = deps.filter(d => nameToPath[d]);
    const depBadge  = knownDeps.length
      ? '<span class="dep-count-badge" title="Depends on: ' + esc(knownDeps.join(', ')) + '">&#128279; ' + knownDeps.length + '</span>'
      : '';
    return '<div class="file-item" id="item_' + id + '">' +
      '<input type="checkbox" id="' + id + '" data-cat="' + cat +
        '" data-path="' + esc(f.path) + '" data-class="' + esc(cls) + '" onchange="onCheck(this)">' +
      '<label class="file-label" for="' + id + '">' +
        '<span class="class-name">' + esc(cls) + depBadge + '</span>' +
        (pkg ? '<span class="pkg-name">' + esc(pkg) + '</span>' : '') +
      '</label>' +
      '</div>';
  }).join('');
}

// ── dependency resolution ──────────────────────────────────────────
function autoDepsEnabled() {
  return document.getElementById('autoDepsToggle').checked;
}

/** Compute transitive closure of deps for a set of class names. */
function transitiveDeps(classNames) {
  const visited = new Set();
  const queue   = [...classNames];
  while (queue.length) {
    const name = queue.shift();
    if (visited.has(name)) continue;
    visited.add(name);
    (depGraph[name] || []).forEach(d => { if (!visited.has(d)) queue.push(d); });
  }
  // Remove the seed classes themselves; return only the deps
  classNames.forEach(n => visited.delete(n));
  return visited;  // Set of class names
}

/** After a manual check change, re-compute autoDepSel and sync checkboxes. */
function syncDeps() {
  if (!autoDepsEnabled()) { autoDepSel = new Set(); return; }

  const manualClasses = [...manualSel].map(p => pathToName[p]).filter(Boolean);
  const depClasses    = transitiveDeps(manualClasses);
  const newAutoPaths  = new Set([...depClasses].map(n => nameToPath[n]).filter(Boolean));

  // Remove auto-dep flag from items no longer needed
  autoDepSel.forEach(p => {
    if (!newAutoPaths.has(p)) {
      const cb = cbByPath(p);
      if (cb && !manualSel.has(p)) {
        cb.checked = false;
        setRowState(cb, false, false);
      }
    }
  });

  autoDepSel = newAutoPaths;

  // Apply auto-dep to newly required items
  autoDepSel.forEach(p => {
    const cb = cbByPath(p);
    if (cb) {
      cb.checked = true;
      setRowState(cb, true, !manualSel.has(p));
    }
  });
}

function cbByPath(path) {
  return document.querySelector('input[data-path="' + CSS.escape(path) + '"]');
}

function setRowState(cb, checked, isAuto) {
  const row = document.getElementById('item_' + cb.id);
  if (!row) return;
  row.classList.toggle('is-checked',   checked);
  row.classList.toggle('is-auto-dep',  checked && isAuto);

  // Add/remove the auto-dep tag inside the label
  const label = row.querySelector('.file-label');
  const existing = label.querySelector('.dep-tag');
  if (checked && isAuto && !existing) {
    const tag = document.createElement('span');
    tag.className = 'dep-tag';
    tag.textContent = '\\u2197 auto-dep';
    label.appendChild(tag);
  } else if ((!checked || !isAuto) && existing) {
    existing.remove();
  }
}

// ── selection helpers ──────────────────────────────────────────────
function onCheck(cb) {
  if (cb.checked) {
    manualSel.add(cb.dataset.path);
    autoDepSel.delete(cb.dataset.path);   // promoted to manual
  } else {
    manualSel.delete(cb.dataset.path);
  }
  setRowState(cb, cb.checked, false);
  syncDeps();
  refreshCounts();
}

function onAutoDepsToggle() {
  syncDeps();
  refreshCounts();
}

function expandAllDeps() {
  syncDeps();
  refreshCounts();
}

function clearAutoDeps() {
  autoDepSel.forEach(p => {
    const cb = cbByPath(p);
    if (cb && !manualSel.has(p)) {
      cb.checked = false;
      setRowState(cb, false, false);
    }
  });
  autoDepSel = new Set();
  refreshCounts();
}

function selAll(cat) {
  boxes(cat).forEach(b => {
    b.checked = true;
    manualSel.add(b.dataset.path);
    setRowState(b, true, false);
  });
  syncDeps();
  refreshCounts();
}
function selNone(cat) {
  boxes(cat).forEach(b => {
    b.checked = false;
    manualSel.delete(b.dataset.path);
    setRowState(b, false, false);
  });
  syncDeps();
  refreshCounts();
}

function boxes(cat) { return [...document.querySelectorAll('input[data-cat="' + cat + '"]')]; }
function selected() { return [...document.querySelectorAll('input[type=checkbox][data-path]:checked')].map(b => b.dataset.path); }
function selectedFiles() {
  return [...document.querySelectorAll('input[type=checkbox][data-path]:checked')]
    .map(b => ({ path: b.dataset.path, category: b.dataset.cat, class_name: b.dataset.class }));
}
function cnt(cat)   { return allFiles.filter(f => f.category === cat).length; }

function refreshCounts() {
  [['Controller','cSel'], ['Service','sSel'], ['DAO','dSel']].forEach(([cat, elId]) => {
    const total = boxes(cat).length;
    const sel   = boxes(cat).filter(b => b.checked).length;
    document.getElementById(elId).textContent = sel + ' / ' + total + ' selected';
  });
  const n = selected().length;
  document.getElementById('convertBtn').disabled = (n === 0);
  const pill = document.getElementById('selSummary');
  pill.textContent = n > 0 ? n + ' file' + (n > 1 ? 's' : '') + ' selected' : '';
  pill.style.display = n > 0 ? '' : 'none';
  updateDepStats();
}

function updateDepStats() {
  const el = document.getElementById('depStats');
  if (!el) return;
  const m = manualSel.size;
  const a = autoDepSel.size;
  if (m === 0 && a === 0) { el.textContent = ''; return; }
  el.textContent = m + ' manual' + (a > 0 ? ' + ' + a + ' auto-dep' : '');
}

// ── convert ────────────────────────────────────────────────────────
async function doConvert() {
  const files = selectedFiles();
  const paths = files.map(f => f.path);
  if (!files.length) { status('Select at least one file first.', 'warning'); return; }

  const outDir = document.getElementById('outDirInput').value.trim() || 'outputs/interactive_selected';
  setConvertBusy(true);
  status('Starting conversion of ' + files.length + ' file(s)\u2026', 'muted');
  openLog();
  const autoCount = paths.filter(p => autoDepSel.has(p)).length;
  const manCount  = files.length - autoCount;
  log('info', 'Converting ' + files.length + ' file(s) \u2192 ' + outDir +
      (autoCount > 0 ? '  (' + manCount + ' selected + ' + autoCount + ' auto-dep)' : ''));

  try {
    const r = await fetch('/convert', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ selected_files: files, output_dir: outDir })
    });

    const reader = r.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const lines = buf.split('\\n');
      buf = lines.pop();
      for (const line of lines) {
        if (!line.trim()) continue;
        if      (line.startsWith('ERROR:'))   log('error', line);
        else if (line.startsWith('WARNING'))  log('warn',  line);
        else if (line.startsWith('DONE'))     log('ok',    '\\u2713 Conversion complete!');
        else                                  log('info',  line);
      }
    }
    if (buf.trim()) log('info', buf);
    status('Done! Check output directory: ' + outDir, 'success');
  } catch(e) {
    log('error', 'Network error: ' + e.message);
    status('Error: ' + e.message, 'danger');
  } finally {
    setConvertBusy(false);
  }
}

// ── log ────────────────────────────────────────────────────────────
function openLog() {
  document.getElementById('logSection').style.display = '';
  document.getElementById('logPanel').innerHTML = '';
}

function log(level, text) {
  const p = document.getElementById('logPanel');
  const now = new Date();
  const ts  = now.toTimeString().slice(0, 8);
  const row = document.createElement('div');
  row.className = 'log-line log-' + level;
  row.innerHTML = '<span class="log-ts">' + ts + '</span><span class="log-msg">' + esc(text) + '</span>';
  p.appendChild(row);
  p.scrollTop = p.scrollHeight;
}

// ── helpers ────────────────────────────────────────────────────────
function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function status(msg, type) {
  const el = document.getElementById('statusBar');
  el.className = 'status-' + type;
  el.textContent = msg;
}

function setScanBusy(b) {
  document.getElementById('scanBtn').disabled = b;
  document.getElementById('scanSpin').classList.toggle('hidden', !b);
}

function setConvertBusy(b) {
  document.getElementById('convertBtn').disabled = b;
  document.getElementById('convertSpin').classList.toggle('hidden', !b);
  if (!b) refreshCounts(); // re-evaluate whether it should re-enable
}

document.getElementById('dirInput').addEventListener('keydown', e => { if (e.key === 'Enter') doScan(); });
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Helpers for multi-group conversion
# ---------------------------------------------------------------------------

import re as _re

_SUFFIX_RE = _re.compile(
    r"(Controller|Service|ServiceImpl|Repository|RepositoryImpl|DAO|DaoImpl|Impl)$",
    _re.IGNORECASE,
)


def _extract_base(class_name: str) -> str:
    """
    Strip common Java role suffixes from a class name and return the lowercase base.

    For example, "CustomerServiceImpl" → "customer", "OrderRepository" → "order".
    Used to group Controller/Service/Repository classes that belong to the same
    domain concept into a single conversion group.

    Args:
        class_name: Java class name (simple, not fully qualified)

    Returns:
        Lowercase base name with role suffix removed
    """
    return _SUFFIX_RE.sub("", class_name).lower()


def _group_selected_files(selected_files: list) -> list:
    """
    Group the user-selected files by base name (strip Controller/Service/Repository etc.).
    Returns a list of groups; each group is a list of file dicts.
    Groups are ordered largest-first.
    """
    groups: dict = {}
    for f in selected_files:
        class_name = f.get("class_name") or Path(f["path"]).stem
        base = _extract_base(class_name) or class_name.lower()
        groups.setdefault(base, []).append(f)
    return sorted(groups.values(), key=lambda g: -len(g))


def _regenerate_index(output_dir_str: str, is_typescript: bool) -> None:
    """
    Regenerate src/index.ts (or .js) to import every controller generated across all groups.

    Called after all conversion groups have completed so that the final entry-point
    wires up every controller that was written to the output directory, regardless of
    which group produced it.  Overwrites any existing index file.

    Args:
        output_dir_str: Absolute path to the root output directory
        is_typescript: True to generate a TypeScript index file (.ts),
            False for JavaScript (.js)
    """
    output_path = Path(output_dir_str)
    ext = ".ts" if is_typescript else ".js"
    ctrl_files = sorted(
        output_path.glob(f"src/presentation/controllers/*.controller{ext}")
    )
    if not ctrl_files:
        return

    lines: list = []
    routes: list = []
    if is_typescript:
        lines.append("import express from 'express';")
        for cf in ctrl_files:
            resource = cf.stem.replace(".controller", "")
            var_name = resource + "Router"
            rel = "presentation/controllers/" + cf.stem
            lines.append(f"import {var_name} from './{rel}';")
            routes.append(f"app.use('/api/{resource}', {var_name});")
        lines += [
            "",
            "const app = express();",
            "const PORT = process.env.PORT ?? 3000;",
            "",
            "app.use(express.json());",
            "app.use(express.urlencoded({ extended: true }));",
            "",
            "// Routes",
            *routes,
            "",
            "app.get('/health', (_req, res) => res.json({ status: 'ok' }));",
            "",
            "app.listen(PORT, () => {",
            "    console.log(`Server running on port ${PORT}`);",
            "});",
            "",
            "export default app;",
            "",
        ]
    else:
        lines.append("const express = require('express');")
        for cf in ctrl_files:
            resource = cf.stem.replace(".controller", "")
            var_name = resource + "Router"
            rel = "presentation/controllers/" + cf.stem
            lines.append(f"const {var_name} = require('./{rel}');")
            routes.append(f"app.use('/api/{resource}', {var_name});")
        lines += [
            "",
            "const app = express();",
            "const PORT = process.env.PORT || 3000;",
            "",
            "app.use(express.json());",
            "app.use(express.urlencoded({ extended: true }));",
            "",
            "// Routes",
            *routes,
            "",
            "app.get('/health', (req, res) => res.json({ status: 'ok' }));",
            "",
            "app.listen(PORT, () => {",
            "    console.log(`Server running on port ${PORT}`);",
            "});",
            "",
            "module.exports = app;",
            "",
        ]

    index_path = output_path / "src" / f"index{ext}"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the single-page file-selection UI."""
    return render_template_string(_HTML)


@app.route("/scan", methods=["POST"])
def scan():
    """
    Scan a Java repository directory and return categorised class metadata.

    Expects a JSON body with a "directory" field pointing to the local Java project
    root.  Parses all Java files, categorises each class (Controller/Service/DAO),
    and builds a dependency graph restricted to the scanned classes.

    Request body:
        {"directory": "/path/to/java/project"}

    Returns:
        JSON with "files" (list of Controller/Service/DAO class descriptors) and
        "dep_graph" (dict mapping class name → list of dependency class names).
        HTTP 400 if directory is missing or invalid; HTTP 500 on parse failure.
    """
    data = request.get_json(force=True) or {}
    directory = (data.get("directory") or "").strip()

    if not directory:
        return jsonify({"error": "No directory provided."}), 400

    target = Path(directory)
    if not target.exists():
        return jsonify({"error": f"Path does not exist: {directory}"}), 400
    if not target.is_dir():
        return jsonify({"error": f"Path is not a directory: {directory}"}), 400

    try:
        scanner = CodeScanner(str(target))
        java_classes = scanner.scan_repository(verbose=False)

        # Build dependency graph across ALL scanned classes (not just the 3 categories)
        mapper = DependencyMapper(java_classes)
        dep_graph_obj = mapper.map_dependencies()

        # Simplify to {ClassName: [DepClassName, ...]} — only classes in our scan
        scanned_names = {cls.name for cls in java_classes}
        dep_graph: dict = {}
        for cls in java_classes:
            deps = [
                d.to_class
                for d in dep_graph_obj.get_dependencies_for_class(cls.name)
                if d.to_class in scanned_names
            ]
            # Deduplicate while preserving order
            seen: set = set()
            unique_deps = []
            for d in deps:
                if d not in seen:
                    seen.add(d)
                    unique_deps.append(d)
            if unique_deps:
                dep_graph[cls.name] = unique_deps

        files = [
            {
                "path": str(Path(cls.file_path).resolve().as_posix()),
                "category": cls.category,
                "class_name": cls.name,
                "package_name": cls.package,
            }
            for cls in java_classes
            if cls.category in ("Controller", "Service", "DAO")
        ]
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify({"files": files, "dep_graph": dep_graph})


@app.route("/save", methods=["POST"])
def save():
    """
    Persist the user's selected file paths to a JSON file on disk.

    Writes a conversion_targets.json file to outputs/interactive_selected/ containing
    the selected source paths.  Primarily used for inspection or as input to external
    tooling; the /convert endpoint handles the actual workflow execution.

    Request body:
        {"selected_paths": ["/abs/path/Foo.java", ...]}

    Returns:
        JSON with "output_file" (path written) and "saved" (count of records).
        HTTP 400 if no files are selected.
    """
    data = request.get_json(force=True) or {}
    selected_paths: list = data.get("selected_paths", [])

    if not selected_paths:
        return jsonify({"error": "No files selected."}), 400

    records = [{"sourcePath": p} for p in selected_paths]
    output_dir = Path(__file__).parent / "outputs" / "interactive_selected"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "conversion_targets.json"
    output_file.write_text(json.dumps(records, indent=2), encoding="utf-8")

    return jsonify({"output_file": str(output_file), "saved": len(records)})


@app.route("/convert", methods=["POST"])
def convert():
    """
    Run the Java-to-Node.js conversion workflow and stream progress to the client.

    Groups selected files by base domain name (stripping role suffixes), then runs
    one LangGraph workflow per group so each domain concept (e.g., Customer) gets its
    own cohesive set of generated files.  After all groups finish, merged analysis
    files are written and a combined index file is regenerated when multiple groups
    were processed.

    Accepts either the new format (selected_files with category metadata) or the
    legacy format (selected_paths plain list).

    Request body:
        {
            "selected_files": [{"path": "...", "category": "...", "class_name": "..."}, ...],
            "output_dir": "outputs/interactive_selected"  // optional
        }

    Returns:
        A streaming plain-text response where each line is prefixed with:
        "INFO:", "WARNING:", "ERROR:", or "DONE".
        HTTP 400 if no files are selected.
    """
    data = request.get_json(force=True) or {}

    # Accept either the new selected_files format or the legacy selected_paths list.
    selected_files: list = data.get("selected_files") or []
    if not selected_files:
        # Backward-compat: plain path list (no category info)
        selected_files = [{"path": p} for p in data.get("selected_paths", [])]

    output_dir_input: str = (data.get("output_dir") or "outputs/interactive_selected").strip()

    if not selected_files:
        return jsonify({"error": "No files selected."}), 400

    def generate():
        """
        Stream generator that runs the conversion and yields progress lines.

        Groups selected files by base name, executes one LangGraph workflow per
        group in a background thread, and yields lines from a thread-safe queue
        as the workflow emits them.  Yields a "DONE\\n" sentinel when finished.
        """
        # Derive the Java source root from the common ancestor of ALL selected files.
        all_paths = [Path(f["path"]) for f in selected_files]
        common = Path(os.path.commonpath([str(p) for p in all_paths]))
        repo_root = str(common if common.is_dir() else common.parent)

        output_dir = Path(output_dir_input).expanduser()
        if not output_dir.is_absolute():
            output_dir = (Path(repo_root) / output_dir).resolve()
        else:
            output_dir = output_dir.resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_dir_str = str(output_dir)

        groups = _group_selected_files(selected_files)
        n_groups = len(groups)

        q: "queue.Queue[object]" = queue.Queue()
        sentinel = object()

        def _node_summary(node_name: str, node_state: dict, prev_state: dict) -> str:
            """
            Produce a human-readable one-line summary for a completed workflow node.

            Each node has a tailored summary that surfaces the most useful metric
            (e.g., file counts, selected class names, dependency totals).  Falls back
            to "[node_name] Completed" for unrecognised nodes.

            Args:
                node_name: LangGraph node name (e.g., "scan_codebase")
                node_state: State dict emitted by the node after it ran
                prev_state: Accumulated state before this node ran, used to compute
                    the delta of newly generated files

            Returns:
                One-line summary string prefixed with "[node_name]"
            """
            if node_name == "scan_codebase":
                count = len(node_state.get("java_classes") or [])
                return f"[scan_codebase] Parsed {count} Java classes from the codebase"

            if node_name == "categorize_classes":
                cats = node_state.get("classes_by_category") or {}
                summary = ", ".join(
                    f"{cat}: {len(lst)}" for cat, lst in sorted(cats.items()) if lst
                ) or "no categories"
                sel = node_state.get("selected_source_classes") or {}
                picked = ", ".join(f"{role}={name}" for role, name in sel.items())
                return f"[categorize_classes] {summary} | selected: {picked}"

            if node_name == "analyze_dependencies":
                graph = node_state.get("dependency_graph") or {}
                total_deps = sum(len(v) for v in graph.values())
                return f"[analyze_dependencies] Mapped {total_deps} dependencies across {len(graph)} classes"

            if node_name == "design_architecture":
                arch = node_state.get("architecture")
                if arch:
                    try:
                        pattern = arch.pattern.value
                    except Exception:
                        pattern = str(arch.pattern)
                    stack = arch.tech_stack
                    return (
                        f"[design_architecture] Pattern: {pattern} | "
                        f"Framework: {stack.framework} | ORM: {stack.orm} | "
                        f"Language: {stack.language}"
                    )
                return "[design_architecture] Architecture designed"

            if node_name == "generate_domain_layer":
                prev_files = set((prev_state.get("generated_files") or {}).keys())
                new_files = set((node_state.get("generated_files") or {}).keys()) - prev_files
                domain_files = [f for f in new_files if "domain" in f or "repository" in f.lower()]
                names = ", ".join(Path(f).name for f in sorted(domain_files)) or "none"
                return f"[generate_domain_layer] Generated {len(domain_files)} file(s): {names}"

            if node_name == "generate_application_layer":
                prev_files = set((prev_state.get("generated_files") or {}).keys())
                new_files = set((node_state.get("generated_files") or {}).keys()) - prev_files
                names = ", ".join(Path(f).name for f in sorted(new_files)) or "none"
                return f"[generate_application_layer] Generated {len(new_files)} file(s): {names}"

            if node_name == "generate_infrastructure_layer":
                prev_files = set((prev_state.get("generated_files") or {}).keys())
                new_files = set((node_state.get("generated_files") or {}).keys()) - prev_files
                names = ", ".join(Path(f).name for f in sorted(new_files)) or "none"
                return f"[generate_infrastructure_layer] Generated {len(new_files)} file(s): {names}"

            if node_name == "generate_presentation_layer":
                prev_files = set((prev_state.get("generated_files") or {}).keys())
                new_files = set((node_state.get("generated_files") or {}).keys()) - prev_files
                ctrl_files = [f for f in new_files if "controller" in f]
                names = ", ".join(Path(f).name for f in sorted(ctrl_files)) or "none"
                return f"[generate_presentation_layer] Generated {len(ctrl_files)} controller(s): {names}"

            if node_name == "generate_config_files":
                prev_files = set((prev_state.get("generated_files") or {}).keys())
                new_files = set((node_state.get("generated_files") or {}).keys()) - prev_files
                names = ", ".join(Path(f).name for f in sorted(new_files)) or "none"
                return f"[generate_config_files] Generated {len(new_files)} config file(s): {names}"

            if node_name == "write_outputs":
                total = len((node_state.get("generated_files") or {}).keys())
                return f"[write_outputs] Wrote {total} file(s) to disk"

            return f"[{node_name}] Completed"

        def run_all_groups() -> None:
            """
            Execute the LangGraph workflow for every conversion group sequentially.

            Runs in a daemon thread.  For each group, creates a fresh initial state,
            streams workflow events into the shared queue, accumulates analysis data,
            and handles error/warning reporting.  After all groups finish, writes merged
            analysis JSON files and regenerates the combined index when needed.
            Puts a sentinel object into the queue when done to signal completion.
            """
            try:
                settings = get_settings()
                total_generated = 0
                any_error = False
                is_typescript = True  # updated from first completed group

                # Accumulators for analysis files that would otherwise be overwritten.
                all_selected_classes: dict = {}       # class_name -> class detail dict
                all_traceability: list = []            # one entry per group

                q.put(f"INFO: Java source root: {repo_root}\n")
                q.put(f"INFO: Output directory: {output_dir_str}\n")
                q.put(f"INFO: {len(selected_files)} file(s) grouped into {n_groups} conversion group(s)\n")

                for group_idx, group in enumerate(groups, 1):
                    group_paths = [f["path"] for f in group]
                    class_names = [
                        f.get("class_name") or Path(f["path"]).stem for f in group
                    ]
                    q.put(
                        f"INFO: ═══ Group {group_idx}/{n_groups}: "
                        f"{', '.join(class_names)} ═══\n"
                    )

                    initial_state = create_initial_state(
                        repo_path=repo_root,
                        output_directory=output_dir_str,
                        target_framework=settings.nodejs_framework,
                        target_orm=settings.orm_preference,
                        llm_provider=settings.llm_provider,
                        verbose=False,
                        skip_tests=True,
                        selected_file_paths=group_paths,
                    )

                    workflow = create_conversion_workflow()
                    accumulated_state = dict(initial_state)

                    for step_output in workflow.stream(initial_state):
                        node_name = list(step_output.keys())[0]
                        node_state = step_output[node_name]
                        try:
                            summary = _node_summary(node_name, node_state, accumulated_state)
                        except Exception:
                            summary = f"[{node_name}] Completed"
                        accumulated_state.update(node_state)
                        q.put(f"INFO: {summary}\n")

                    for err in accumulated_state.get("errors", []):
                        step = err.get("step", "?")
                        msg = err.get("error", str(err))
                        q.put(f"ERROR: [{step}] {msg}\n")
                        any_error = True

                    for warn in accumulated_state.get("warnings", []):
                        q.put(f"WARNING: {warn}\n")

                    group_files = accumulated_state.get("generated_files", {})
                    total_generated += len(group_files)

                    # Detect whether the project is TypeScript or JavaScript
                    if any(k.endswith(".ts") for k in group_files):
                        is_typescript = True
                    elif any(k.endswith(".js") for k in group_files):
                        is_typescript = False

                    # ── Accumulate analysis data ──────────────────────────────
                    # selected_source_classes.json: merge by class name so every
                    # group's entries survive instead of the last one winning.
                    raw_ssc = group_files.get("analysis/selected_source_classes.json")
                    if raw_ssc:
                        try:
                            ssc = json.loads(raw_ssc)
                            # ssc is {role: {name, ...}, ...}  →  key by class name
                            for role_data in ssc.values():
                                cls_name = role_data.get("name", "unknown")
                                all_selected_classes[cls_name] = role_data
                        except Exception:
                            pass

                    # conversion_traceability.json: keep one entry per group
                    raw_trace = group_files.get("analysis/conversion_traceability.json")
                    if raw_trace:
                        try:
                            trace = json.loads(raw_trace)
                            trace["_group"] = group_idx
                            trace["_classes"] = class_names
                            all_traceability.append(trace)
                        except Exception:
                            pass

                    q.put(
                        f"INFO: Group {group_idx}/{n_groups} done — "
                        f"{len(group_files)} file(s) written\n"
                    )

                # ── Write merged analysis files ───────────────────────────────
                analysis_dir = Path(output_dir_str) / "analysis"
                analysis_dir.mkdir(parents=True, exist_ok=True)

                if all_selected_classes:
                    (analysis_dir / "selected_source_classes.json").write_text(
                        json.dumps(all_selected_classes, indent=2), encoding="utf-8"
                    )

                if all_traceability:
                    (analysis_dir / "conversion_traceability.json").write_text(
                        json.dumps(all_traceability, indent=2), encoding="utf-8"
                    )

                q.put(f"INFO: Merged analysis files written ({len(all_selected_classes)} class(es) tracked)\n")

                # ── Regenerate combined index after all groups ────────────────
                if n_groups > 1:
                    try:
                        _regenerate_index(output_dir_str, is_typescript)
                        ext = "ts" if is_typescript else "js"
                        q.put(f"INFO: Regenerated combined src/index.{ext} for all {n_groups} groups\n")
                    except Exception as idx_err:
                        q.put(f"WARNING: Could not regenerate index file: {idx_err}\n")

                q.put(f"INFO: Total files generated: {total_generated}\n")
                q.put(f"INFO: Output written to: {output_dir_str}\n")
                if not any_error:
                    q.put("INFO: All conversions completed successfully.\n")
                q.put("DONE\n")

            except Exception as exc:
                q.put(f"ERROR: Workflow failed: {exc}\n")
                q.put("DONE\n")
            finally:
                q.put(sentinel)

        t = threading.Thread(target=run_all_groups, daemon=True)
        t.start()

        while True:
            item = q.get()
            if item is sentinel:
                break
            yield item  # type: ignore[misc]

    return Response(
        stream_with_context(generate()),
        mimetype="text/plain",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Java -> Node File Selector UI")
    print("Open  http://localhost:5050  in your browser.\n")
    app.run(host="127.0.0.1", port=5050, debug=False, threaded=True)
