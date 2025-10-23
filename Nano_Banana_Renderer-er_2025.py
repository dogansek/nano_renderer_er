#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rhino 8 CPython Script: Nano 🍌 Chat Renderer
=================================================

Chat-like iterative viewport image generator with Google Gemini 2.5 Flash Image AI.
Supports unrestricted generation with structured viewport capture for clean studio results.

Requirements:
    pip install google-genai

Installation:
1. Save this file as "nano_banana_chat_renderer.py"
2. Open Rhino 8
3. Run the script using the ScriptEditor or drag-and-drop into viewport

Workflow:
1. Capture & Process Viewport - Captures clean viewport and automatically generates studio result (PURGES MEMORY)
2. Generate - Create unrestricted images based on Primary Reference (preserves memory for iterations)
3. Iterate - Replace Primary Reference with result (PRESERVES MEMORY - continues Prompt)

Two Generation Modes:
- Capture & Process Viewport: Clean studio rendering with structured prompt and camera info
- Generate: Completely unrestricted generation based on user prompts

Features:
- **DUAL MODE WORKFLOW**: Studio capture vs unrestricted generation
- **SMART MEMORY MANAGEMENT**: 
  - Iterate: Preserves Prompt context and memory for continuous refinement
  - Capture & Process: Purges memory and generates clean studio result automatically
- **CLEAN VIEWPORT CAPTURE**: No grid lines, curves, or edges in background
- **UNRESTRICTED GENERATION**: Complete creative freedom with user prompts
- Iterate button replaces Primary Reference with Generated Result
- Prompt log tracks each input and output with full context
- Automatic camera information extraction (lens length, type, FOV)
- Up to 4 mood board images for style guidance
- Updated cost tracking with current Gemini 2.5 Flash Image pricing ($0.039/image)
- Session and cumulative usage monitoring
- Render timer functionality
- Large preview area for generated results
- Persistent settings storage
- Full-size image viewer with Save As functionality

Pricing (as of September 2025):
- Input: $0.30 per 1M tokens (text/image/video)
- Output: $2.50 per 1M tokens (including thinking tokens)
- Image Generation: $0.039 per image (1290 tokens @ $30/1M output tokens)

Version: 4.1 - Fixed Window Edition
Date: October 2025
Tested: macOS Rhino 8 with CPython
"""

import os
import sys
import io
import base64
import mimetypes
import json
import time
from pathlib import Path

# Rhino / .NET (pythonnet)
import Rhino
import scriptcontext as sc
import Rhino.Display as rdisplay
import Rhino.UI as rui
import Eto.Forms as Forms
from Eto.Forms import TextAlignment
import Eto.Drawing as Drawing
import System
import System.Drawing as SD
import System.Drawing.Imaging as Imaging

# Settings file path
SETTINGS_FILE = Path.home() / "Documents" / "RhinoGeminiSettings.json"


def load_settings():
    """Load settings from JSON file."""
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Failed to load settings: {e}")
    
    # Default settings
    return {
        "api_key": "",
        "output_folder": str(get_default_save_dir()),
        "prompt": "",
        "total_tokens_used": 0,
        "total_cost": 0.0
    }


def save_settings(settings):
    """Save settings to JSON file."""
    try:
        SETTINGS_FILE.parent.mkdir(exist_ok=True)
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        print(f"Failed to save settings: {e}")


def bitmap_to_png_bytes(bmp):
    """Convert .NET Bitmap to Python bytes (PNG format)."""
    try:
        ms = System.IO.MemoryStream()
        bmp.Save(ms, Imaging.ImageFormat.Png)
        # Convert .NET byte[] to Python bytes
        data = ms.ToArray()
        return bytes(bytearray(data))
    except Exception as e:
        raise RuntimeError(f"Failed to convert bitmap to PNG bytes: {e}")


def read_file_as_part(path):
    """Read file as bytes with MIME type for Gemini API."""
    from google.genai import types
    
    if not path:
        return None
    
    path_obj = Path(path)
    if not path_obj.is_file():
        return None
    
    mime_type, _ = mimetypes.guess_type(str(path_obj))
    if mime_type is None:
        mime_type = "application/octet-stream"
    
    try:
        with open(path_obj, "rb") as f:
            data = f.read()
        return types.Part.from_bytes(data=data, mime_type=mime_type)
    except Exception as e:
        print(f"Warning: Failed to read file {path}: {e}")
        return None


def extract_camera_info(viewport):
    """Extract camera information from Rhino viewport."""
    try:
        camera_info = {}
        
        # Try to get viewport info
        vp_info = None
        if hasattr(viewport, 'ViewportInfo'):
            vp_info = viewport.ViewportInfo
        elif hasattr(viewport, 'GetViewportInfo'):
            vp_info = viewport.GetViewportInfo()
        
        # If we couldn't get viewport info, try direct access to viewport properties
        if vp_info is None:
            # Try direct access to viewport properties
            try:
                if hasattr(viewport, 'IsPerspectiveProjection'):
                    camera_info['type'] = 'perspective' if viewport.IsPerspectiveProjection else 'parallel'
                
                if hasattr(viewport, 'Camera35mmLensLength'):
                    lens_length = viewport.Camera35mmLensLength
                    camera_info['lens_length'] = f"{lens_length:.1f}mm"
                    
                    # Categorize lens type
                    if lens_length < 24:
                        camera_info['lens_type'] = 'ultra-wide angle'
                    elif lens_length < 35:
                        camera_info['lens_type'] = 'wide angle'
                    elif lens_length < 85:
                        camera_info['lens_type'] = 'normal'
                    elif lens_length < 135:
                        camera_info['lens_type'] = 'short telephoto'
                    else:
                        camera_info['lens_type'] = 'telephoto'
                
                if hasattr(viewport, 'CameraAngle'):
                    fov_radians = viewport.CameraAngle
                    fov_degrees = fov_radians * 180.0 / 3.14159
                    camera_info['field_of_view'] = f"{fov_degrees:.1f}°"
                
                # Return what we found
                if camera_info:
                    return camera_info
                    
            except Exception:
                pass
            
            # Last resort fallback
            camera_info['type'] = 'unknown'
            camera_info['lens_length'] = 'unknown'
            camera_info['lens_type'] = 'unknown'
            camera_info['field_of_view'] = 'unknown'
            return camera_info
        
        # Camera type
        if hasattr(vp_info, 'IsPerspectiveProjection') and vp_info.IsPerspectiveProjection:
            camera_info['type'] = 'perspective'
        elif hasattr(vp_info, 'IsParallelProjection') and vp_info.IsParallelProjection:
            camera_info['type'] = 'parallel'
        else:
            camera_info['type'] = 'unknown'
        
        # Lens length (focal length) - only meaningful for perspective views
        if camera_info['type'] == 'perspective' and hasattr(vp_info, 'Camera35mmLensLength'):
            lens_length = vp_info.Camera35mmLensLength
            camera_info['lens_length'] = f"{lens_length:.1f}mm"
            
            # Categorize lens type for better AI understanding
            if lens_length < 24:
                camera_info['lens_type'] = 'ultra-wide angle'
            elif lens_length < 35:
                camera_info['lens_type'] = 'wide angle'
            elif lens_length < 85:
                camera_info['lens_type'] = 'normal'
            elif lens_length < 135:
                camera_info['lens_type'] = 'short telephoto'
            else:
                camera_info['lens_type'] = 'telephoto'
        else:
            camera_info['lens_length'] = 'N/A (parallel projection)'
            camera_info['lens_type'] = 'orthographic'
        
        # Field of view
        if hasattr(vp_info, 'CameraAngle'):
            fov_radians = vp_info.CameraAngle
            fov_degrees = fov_radians * 180.0 / 3.14159
            camera_info['field_of_view'] = f"{fov_degrees:.1f}°"
        
        return camera_info
        
    except Exception as e:
        return {
            'type': 'unknown',
            'lens_length': 'unknown',
            'lens_type': 'unknown',
            'field_of_view': 'unknown'
        }


def capture_active_view_shaded(width=None, height=None):
    """Capture active viewport as PNG bytes, temporarily set to Shaded mode with clean background. Returns bitmap, PNG bytes, and camera info."""
    view = sc.doc.Views.ActiveView
    if view is None:
        raise RuntimeError("No active view to capture.")

    vp = view.ActiveViewport
    orig_mode = vp.DisplayMode

    # Extract camera information before capture
    camera_info = extract_camera_info(vp)

    # Find Shaded display mode
    shaded_dm = rdisplay.DisplayModeDescription.FindByName("Shaded")
    if shaded_dm is None:
        raise RuntimeError("Couldn't find 'Shaded' display mode.")

    # Store original curve display settings
    orig_curves_visible = []
    try:
        # Temporarily hide all curve objects
        for obj in sc.doc.Objects:
            if obj.ObjectType == Rhino.DocObjects.ObjectType.Curve:
                was_visible = obj.Attributes.Visible
                orig_curves_visible.append((obj.Id, was_visible))
                if was_visible:
                    obj.Attributes.Visible = False
                    obj.CommitChanges()
    except Exception as e:
        print(f"Warning: Could not hide curves: {e}")

    try:
        # Switch to Shaded mode
        vp.DisplayMode = shaded_dm
        view.Redraw()

        # Use view size unless custom provided
        size = vp.Size
        w = int(width or size.Width)
        h = int(height or size.Height)
        
        # Ensure minimum size
        w = max(w, 64)
        h = max(h, 64)
        
        # Default size if too small
        if w < 64:
            w = 1024
        if h < 64:
            h = 1024

        # Configure capture with clean background
        vc = rdisplay.ViewCapture()
        vc.Width = w
        vc.Height = h
        vc.ScaleScreenItems = False
        vc.DrawAxes = False
        vc.DrawGrid = False
        vc.DrawGridAxes = False
        vc.DrawWorldAxes = False
        vc.DrawCPlaneGrid = False
        vc.DrawBackground = True
        vc.TransparentBackground = False
        
        # Capture the bitmap
        bmp = vc.CaptureToBitmap(view)
        if bmp is None:
            raise RuntimeError("Capture returned None.")
        
        return bmp, bitmap_to_png_bytes(bmp), camera_info
        
    finally:
        # Restore curve visibility
        try:
            for obj_id, was_visible in orig_curves_visible:
                obj = sc.doc.Objects.FindId(obj_id)
                if obj and obj.Attributes.Visible != was_visible:
                    obj.Attributes.Visible = was_visible
                    obj.CommitChanges()
        except Exception as e:
            print(f"Warning: Could not restore curve visibility: {e}")
        
        # Restore original display mode
        try:
            vp.DisplayMode = orig_mode
            view.Redraw()
        except Exception as e:
            print(f"Warning: Failed to restore original display mode: {e}")


def get_default_save_dir():
    """Get default directory to save result images."""
    if sc.doc.Path and Path(sc.doc.Path).parent.exists():
        return str(Path(sc.doc.Path).parent)
    
    # Fallback to Pictures directory
    pictures_dir = Path.home() / "Pictures"
    pictures_dir.mkdir(exist_ok=True)
    return str(pictures_dir)


class NanoBananaChatForm(Forms.Form):
    """Chat-like UI form for iterative Gemini viewport integration."""
    
    def __init__(self):
        super().__init__()
        self.Title = "Nano 🍌 Viewport Renderer-er V2"
        self.Size = Drawing.Size(640, 900)
        self.Resizable = False
        self.Padding = Drawing.Padding(10)
        
        # Make window always stay on top of ALL windows (aggressive mode)
        self.Topmost = True  # Always on top of everything
        self.ShowInTaskbar = False  # Don't show in taskbar
        try:
            # Set Rhino as the owner so dialog minimizes/restores with Rhino
            import Rhino.UI
            rhino_window = Rhino.UI.RhinoEtoApp.MainWindow
            if rhino_window is not None:
                self.Owner = rhino_window
        except Exception:
            pass
        
        # Set icon if available
        try:
            self.Icon = rui.Icon.IconFromResource("Rhino.App.ico")
        except Exception:
            self.Icon = None

        # Load settings
        self.settings = load_settings()
        
        # Model pricing configuration (per 1M tokens in USD)
        # Source: https://ai.google.dev/gemini-api/docs/pricing (September 2025)
        # Gemini 2.5 Flash Image blog: https://developers.googleblog.com/en/introducing-gemini-2-5-flash-image/
        self.model_pricing = {
            "gemini-2.5-flash-image-preview": {
                "input_price": 0.30,  # $0.30 per 1M tokens (text/image/video)
                "output_price": 2.50,  # $2.50 per 1M tokens (including thinking tokens)
                "image_generation_price": 30.00,  # $30.00 per 1M output tokens for images
                "tokens_per_image": 1290,  # Each generated image consumes 1290 tokens
                "cost_per_image": 0.039  # $0.039 per image (1290 * $30/1M)
            },
            "gemini-2.0-flash": {
                "input_price": 0.10,  # $0.10 per 1M tokens (text/image/video)
                "output_price": 0.40,  # $0.40 per 1M tokens
                "image_generation_price": 30.00,  # $30.00 per 1M output tokens for images
                "tokens_per_image": 1290,  # Each generated image consumes 1290 tokens
                "cost_per_image": 0.039  # $0.039 per image (1290 * $30/1M)
            }
        }
        
        # Fixed model
        self.model = "gemini-2.5-flash-image-preview"
        
        # Timer state
        self.render_start_time = None
        self.timer_running = False
        
        # Chat Prompt counter and memory
        self.Prompt_step = 0
        self.Prompt_history = []  # Stores Prompt context for iterations
        
        # Initialize UI components
        self._setup_widgets()
        self._setup_layout()
        
        # State variables
        self._last_generated_image_path = None
        self._last_viewport_bitmap = None
        self._captured_viewport_bytes = None
        self._camera_info = None
        self._viewport_captured = False
        self._first_capture = True  # Track if this is the first capture
        
        # Set initial prompt state - disabled until viewport captured
        self._update_prompt_state()

    def _get_model_pricing(self, model_name=None):
        """Get pricing information for specified model or current model."""
        model = model_name or self.model
        return self.model_pricing.get(model, self.model_pricing["gemini-2.5-flash-image-preview"])

    def _calculate_generation_cost(self, input_tokens, output_tokens, model_name=None):
        """Calculate total cost for a generation including image cost."""
        pricing = self._get_model_pricing(model_name)
        
        # Standard token costs
        input_cost = (input_tokens / 1_000_000) * pricing["input_price"]
        output_cost = (output_tokens / 1_000_000) * pricing["output_price"] 
        
        # Fixed image generation cost
        image_cost = pricing["cost_per_image"]
        
        return {
            "input_cost": input_cost,
            "output_cost": output_cost, 
            "image_cost": image_cost,
            "total_cost": input_cost + output_cost + image_cost,
            "pricing_info": pricing
        }

    def _setup_widgets(self):
        """Initialize all UI widgets."""
        # API Key input
        self.api_key_tb = Forms.PasswordBox()
        self.api_key_tb.Text = self.settings.get("api_key", "")
        self.api_key_tb.Size = Drawing.Size(425, -1)
        
        self.save_api_key_cb = Forms.CheckBox()
        self.save_api_key_cb.Text = "Save API Key"
        
        # Output folder selection
        self.output_folder_tb = Forms.TextBox()
        self.output_folder_tb.Text = self.settings.get("output_folder", get_default_save_dir())
        self.output_folder_tb.ReadOnly = True
        self.output_folder_tb.Size = Drawing.Size(425, -1)
        
        self.browse_folder_btn = Forms.Button()
        self.browse_folder_btn.Text = "Browse..."
        self.browse_folder_btn.Size = Drawing.Size(116, -1)
        self.browse_folder_btn.Click += self.on_browse_folder

        # Chat log section (larger, moved to top)
        self.chat_log_tb = Forms.TextArea()
        self.chat_log_tb.ReadOnly = True
        self.chat_log_tb.Size = Drawing.Size(425, 740)
        self.chat_log_tb.Font = Drawing.Fonts.Monospace(10)
        self.chat_log_tb.Text = "Welcome to Nano 🍌 Viewport Renderer-er 2.0! Designed & Developed by S. Dogan Sekercioglu.\n\n"

        # Single prompt input area - STARTS DISABLED
        self.prompt_tb = Forms.TextArea()
        self.prompt_tb.Size = Drawing.Size(580, 180)
        self.prompt_tb.Wrap = True
        self.prompt_tb.Enabled = False  # Disabled until viewport captured
        
        # Store placeholder state
        self._prompt_placeholder_active = True
        self._prompt_ever_focused = False  # Track if prompt has ever been focused
        self._prompt_placeholder_text = """Capture active viewport to start creating!

Quick Guide:
• Capture: Clean clay render based only on the viewport
• Generate: Variations with your prompt + mood board
• Iterate: Move generated variation to primary reference for further refinement"""
        
        # Set initial placeholder appearance
        self.prompt_tb.Text = self._prompt_placeholder_text
        self.prompt_tb.TextColor = Drawing.Colors.Gray
        
        # Setup focus handlers for placeholder behavior
        def on_prompt_focus(sender, e):
            if self._prompt_placeholder_active and self.prompt_tb.Enabled:
                self.prompt_tb.Text = ""
                self.prompt_tb.TextColor = Drawing.SystemColors.ControlText
                self._prompt_placeholder_active = False
                self._prompt_ever_focused = True  # Mark as focused
        
        def on_prompt_blur(sender, e):
            # Only restore placeholder if it has never been focused before
            if not self._prompt_ever_focused and not self.prompt_tb.Text.strip():
                self.prompt_tb.Text = self._prompt_placeholder_text
                self.prompt_tb.TextColor = Drawing.Colors.Gray
                self._prompt_placeholder_active = True
        
        self.prompt_tb.GotFocus += on_prompt_focus
        self.prompt_tb.LostFocus += on_prompt_blur


        # Reference image controls (up to 4) - MOOD BOARD
        self._build_reference_controls()

        # Go Bananas checkbox
        self.go_bananas_cb = Forms.CheckBox()
        self.go_bananas_cb.Text = "Go Bananas!"
        self.go_bananas_cb.ToolTip = "Remove all base prompts and restrictions for creative freedom"

        # Main action buttons - CHAT WORKFLOW
        self.capture_viewport_btn = Forms.Button()
        self.capture_viewport_btn.Text = "Capture 📷"
        self.capture_viewport_btn.Size = Drawing.Size(-1, 30)
        self.capture_viewport_btn.Click += self.on_capture_viewport
        
        self.generate_btn = Forms.Button()
        self.generate_btn.Text = "Generate 🪄"
        self.generate_btn.Size = Drawing.Size(-1, 30)
        self.generate_btn.Enabled = False  # Disabled until viewport processed
        self.generate_btn.Click += self.on_generate
        
        self.iterate_btn = Forms.Button()
        self.iterate_btn.Text = "Iterate 🔄"
        self.iterate_btn.Size = Drawing.Size(-1, 30)
        self.iterate_btn.Enabled = False  # Disabled until image generated
        self.iterate_btn.ToolTip = "Replace Primary Reference with Generated Result for next iteration"
        self.iterate_btn.Click += self.on_iterate
        
        # Timer display
        self.timer_label = Forms.Label()
        self.timer_label.Text = "Timer: 00:00"
        self.timer_label.Size = Drawing.Size(155, 30)
        self.timer_label.TextAlignment = TextAlignment.Center
        self.timer_label.BackgroundColor = Drawing.Colors.Transparent
        self.timer_label.Font = Drawing.Fonts.Sans(10, Drawing.FontStyle.Bold)
        
        self.show_generated_btn = Forms.Button()
        self.show_generated_btn.Text = "Show Last Generated"
        self.show_generated_btn.Size = Drawing.Size(580, 30)
        self.show_generated_btn.Enabled = False
        self.show_generated_btn.Click += self.on_show_generated

        # Preview panels - NO TITLES IN GROUPBOX
        # Primary Reference preview (shows processed viewport result)
        self.viewport_preview = Forms.ImageView()
        self.viewport_preview.Size = Drawing.Size(275, 172)
        self.viewport_preview.Image = None
        
        self.viewport_panel = Forms.GroupBox()
        self.viewport_panel.Content = self.viewport_preview
        self.viewport_panel.Size = Drawing.Size(280, 177)
        self.viewport_panel.Text = ""
        self.viewport_panel.Padding = Drawing.Padding(2)

        # Generated Result preview with border
        self.result_preview = Forms.ImageView()
        self.result_preview.Size = Drawing.Size(275, 172)
        self.result_preview.Image = None
        
        self.result_panel = Forms.GroupBox()
        self.result_panel.Content = self.result_preview
        self.result_panel.Size = Drawing.Size(280, 177)
        self.result_panel.Text = ""
        self.result_panel.Padding = Drawing.Padding(2)

        # Status bar for token/cost tracking
        self._setup_status_bar()
        
        # Setup timer update mechanism
        self._setup_timer()

    def _setup_timer(self):
        """Setup timer update mechanism."""
        try:
            # Use threading timer instead of UITimer for better compatibility
            import threading
            self.timer_thread = None
            self.timer_stop_event = None
        except Exception as e:
            print(f"Warning: Could not setup timer: {e}")

    def _start_timer(self):
        """Start the render timer."""
        try:
            import threading
            self.render_start_time = time.time()
            self.timer_running = True
            
            # Stop any existing timer
            if self.timer_thread and self.timer_thread.is_alive():
                if self.timer_stop_event:
                    self.timer_stop_event.set()
                self.timer_thread.join(timeout=1.0)
            
            # Create new stop event and timer thread
            self.timer_stop_event = threading.Event()
            self.timer_thread = threading.Thread(target=self._timer_worker)
            self.timer_thread.daemon = True
            self.timer_thread.start()
            
        except Exception as e:
            print(f"Warning: Could not start timer: {e}")

    def _stop_timer(self):
        """Stop the render timer."""
        try:
            self.timer_running = False
            if self.timer_stop_event:
                self.timer_stop_event.set()
            if self.timer_thread and self.timer_thread.is_alive():
                self.timer_thread.join(timeout=1.0)
            
            # Show final time in same format
            if self.render_start_time:
                elapsed = time.time() - self.render_start_time
                minutes = int(elapsed // 60)
                seconds = int(elapsed % 60)
                self.timer_label.Text = f"Timer: {minutes:02d}:{seconds:02d}"
        except Exception as e:
            print(f"Warning: Could not stop timer: {e}")

    def _timer_worker(self):
        """Timer worker thread that updates the display."""
        try:
            while self.timer_running and not self.timer_stop_event.is_set():
                if self.render_start_time:
                    elapsed = time.time() - self.render_start_time
                    minutes = int(elapsed // 60)
                    seconds = int(elapsed % 60)
                    timer_text = f"Timer: {minutes:02d}:{seconds:02d}"
                    
                    # Update UI on main thread
                    try:
                        # Use Application.Instance.AsyncInvoke for thread-safe UI updates
                        if hasattr(Forms.Application, 'Instance') and Forms.Application.Instance:
                            Forms.Application.Instance.AsyncInvoke(lambda: setattr(self.timer_label, 'Text', timer_text))
                        else:
                            # Fallback: direct assignment (may not be thread-safe)
                            self.timer_label.Text = timer_text
                    except Exception:
                        # If UI update fails, continue loop
                        pass
                
                # Wait 1 second or until stop event
                self.timer_stop_event.wait(1.0)
        except Exception as e:
            print(f"Warning: Timer worker error: {e}")

    def _build_reference_controls(self):
        """Build mood board image controls with previews - UPDATED ASPECT RATIO."""
        # Mood board image previews with borders
        self.ref_previews = []
        self.ref_preview_panels = []
        self.ref_file_btns = []
        self.ref_clear_btns = []
        
        # Scaled down dimensions proportionally
        preview_width = 92
        preview_height = 58
        panel_width = 97
        panel_height = 63
        button_width = 44
        button_height = 22
        
        for i in range(4):
            # Create ImageView with fixed size
            preview = Forms.ImageView()
            preview.Size = Drawing.Size(preview_width, preview_height)
            preview.Image = None
            self.ref_previews.append(preview)
            
            # Create bordered panel for preview with fixed size
            preview_panel = Forms.GroupBox()
            preview_panel.Content = preview
            preview_panel.Size = Drawing.Size(panel_width, panel_height)
            preview_panel.Text = ""
            preview_panel.Padding = Drawing.Padding(3)
            self.ref_preview_panels.append(preview_panel)
            
            # File picker button with fixed size
            file_btn = Forms.Button()
            file_btn.Text = "..."
            file_btn.Size = Drawing.Size(button_width, button_height)
            file_btn.Click += lambda s, e, idx=i: self._select_reference_image(idx)
            self.ref_file_btns.append(file_btn)
            
            # Clear button with fixed size
            clear_btn = Forms.Button()
            clear_btn.Text = "X"
            clear_btn.Size = Drawing.Size(button_width, button_height)
            clear_btn.Click += lambda s, e, idx=i: self._clear_reference_image(idx)
            self.ref_clear_btns.append(clear_btn)

    def _setup_status_bar(self):
        """Setup status bar for token and cost tracking."""
        # Session tracking
        self.session_tokens = 0
        self.session_cost = 0.0
        
        # Status bar labels - same size as timer (10pt)
        pricing = self._get_model_pricing()
        self.status_model_label = Forms.Label()
        self.status_model_label.Text = f"Model: 2.5 Flash (${pricing['cost_per_image']:.3f}/img)"
        self.status_model_label.Font = Drawing.Fonts.Sans(10)
        
        self.status_session_label = Forms.Label()
        self.status_session_label.Text = "Session: $0.00"
        self.status_session_label.Font = Drawing.Fonts.Sans(10)
        
        self.status_total_label = Forms.Label()
        total_cost = self.settings.get("total_cost", 0.0)
        self.status_total_label.Text = f"Total: ${total_cost:.2f}"
        self.status_total_label.Font = Drawing.Fonts.Sans(10)

    def _create_label(self, text):
        """Helper method to create labels."""
        label = Forms.Label()
        label.Text = text
        label.TextAlignment = TextAlignment.Left
        return label

    def _create_separator(self):
        """Create a horizontal separator line."""
        separator = Forms.Panel()
        separator.BackgroundColor = Drawing.Colors.Gray
        separator.Size = Drawing.Size(425, 1)
        return separator

    def _update_prompt_state(self):
        """Update prompt box state based on viewport capture status."""
        if self._viewport_captured:
            self.prompt_tb.Enabled = True
            # Only restore placeholder if it has never been focused before
            if not self._prompt_ever_focused:
                if not self.prompt_tb.Text.strip() or self.prompt_tb.Text == self._prompt_placeholder_text:
                    self.prompt_tb.Text = self._prompt_placeholder_text
                    self.prompt_tb.TextColor = Drawing.Colors.Gray
                    self._prompt_placeholder_active = True
        else:
            self.prompt_tb.Enabled = False
            if not self._prompt_ever_focused:
                self.prompt_tb.Text = self._prompt_placeholder_text
                self.prompt_tb.TextColor = Drawing.Colors.Gray
                self._prompt_placeholder_active = True

    def _setup_layout(self):
        """Setup the main layout - TABBED INTERFACE."""
        # Main container
        main_layout = Forms.DynamicLayout()
        main_layout.DefaultSpacing = Drawing.Size(0, 0)
        
        # Create tab control
        tabs = Forms.TabControl()
        tabs.Size = Drawing.Size(580, 825)
        
        # Tab 1: Render
        render_tab = Forms.TabPage()
        render_tab.Text = "Render"
        render_tab.Content = self._create_render_tab()
        tabs.Pages.Add(render_tab)
        
        # Tab 2: Prompt Log
        log_tab = Forms.TabPage()
        log_tab.Text = "Prompt Log"
        log_tab.Content = self._create_log_tab()
        tabs.Pages.Add(log_tab)
        
        # Tab 3: Setup
        setup_tab = Forms.TabPage()
        setup_tab.Text = "Setup"
        setup_tab.Content = self._create_setup_tab()
        tabs.Pages.Add(setup_tab)
        
        # Tab 4: About
        about_tab = Forms.TabPage()
        about_tab.Text = "About"
        about_tab.Content = self._create_about_tab()
        tabs.Pages.Add(about_tab)
        
        # Add tabs to main layout
        main_layout.AddRow(tabs)
        
        # Status bar at bottom (visible in all tabs)
        status_bar = Forms.DynamicLayout()
        status_bar.DefaultSpacing = Drawing.Size(5, 5)
        status_bar.Padding = Drawing.Padding(0, 8, 0, 0)

        
        status_row = Forms.DynamicLayout()
        status_row.DefaultSpacing = Drawing.Size(5, 0)
        status_row.AddRow(
            self.status_model_label,
            self.status_session_label,
            self.status_total_label
        )
        status_bar.Add(status_row)
        
        main_layout.AddRow(status_bar)
        
        # Set main content
        self.Content = main_layout

    def _create_render_tab(self):
        """Create the Render tab content."""
        layout = Forms.DynamicLayout()
        layout.DefaultSpacing = Drawing.Size(10, 15)
        layout.Padding = Drawing.Padding(16)
        
        # 1. PROMPT SECTION
        prompt_section = Forms.DynamicLayout()
        prompt_section.DefaultSpacing = Drawing.Size(0, 8)
        prompt_section.AddRow(self._create_label("Prompt:"))
        prompt_section.AddRow(self.prompt_tb)
        layout.Add(prompt_section)
        
        # 2. ACTION BUTTONS (evenly distributed)
        button_table = Forms.TableLayout()
        button_table.Spacing = Drawing.Size(8, 0)
        button_table.Rows.Add(Forms.TableRow(
            Forms.TableCell(self.capture_viewport_btn, True),
            Forms.TableCell(self.generate_btn, True),
            Forms.TableCell(self.iterate_btn, True)
        ))
        
        layout.Add(button_table)
        layout.AddRow(self.show_generated_btn)
        
        # 3. PREVIEW SECTION
        preview_section = Forms.DynamicLayout()
        preview_section.DefaultSpacing = Drawing.Size(0, 8)
        
        # Headers
        header_table = Forms.TableLayout()
        header_table.Spacing = Drawing.Size(10, 0)
        primary_ref_label = self._create_label("Primary Reference:")
        generated_result_label = self._create_label("Generated Result:")
        header_table.Rows.Add(Forms.TableRow(
            Forms.TableCell(primary_ref_label, True),
            Forms.TableCell(generated_result_label, True)
        ))
        preview_section.Add(header_table)
        
        # Image panels
        preview_table = Forms.TableLayout()
        preview_table.Spacing = Drawing.Size(10, 0)
        
        viewport_column = Forms.DynamicLayout()
        viewport_column.DefaultSpacing = Drawing.Size(0, 0)
        viewport_column.AddRow(self.viewport_panel)
        
        result_column = Forms.DynamicLayout()
        result_column.DefaultSpacing = Drawing.Size(0, 0)
        result_column.AddRow(self.result_panel)
        
        preview_table.Rows.Add(Forms.TableRow(
            Forms.TableCell(viewport_column, True),
            Forms.TableCell(result_column, True)
        ))
        preview_section.Add(preview_table)
        layout.Add(preview_section)
        
        # 4. MOOD BOARD SECTION (4 columns × 2 rows; top = image 16:9, bottom = controls)
        layout.AddRow(self._create_separator())

        # Title row for Mood Board (fixed 4-cell row, matching "Primary Reference:" style)
        title_label = Forms.Label()
        title_label.Text = 'Mood Board:'
        title_label.HorizontalAlignment = Forms.HorizontalAlignment.Left

        title_row = Forms.TableLayout()
        title_row.Spacing = Drawing.Size(10, 0)
        _ph1 = Forms.Label(); _ph1.Text = ''
        _ph2 = Forms.Label(); _ph2.Text = ''
        _ph3 = Forms.Label(); _ph3.Text = ''
        title_row.Rows.Add(Forms.TableRow(
            Forms.TableCell(title_label, False),
            Forms.TableCell(_ph1, False),
            Forms.TableCell(_ph2, False),
            Forms.TableCell(_ph3, False)
        ))
        layout.Add(title_row)

        # Compute column width to fit inside the tab (~580 px content width)
        # Keep existing gaps (assumed ~8 px); adjust only if your tab padding differs
        col_gap = 10
        content_w = 580
        col_w = int((content_w - 3 * col_gap) / 4)
        img_w = col_w
        img_h = int(round(img_w * 9.0 / 16.0))  # 16:9

        # Ensure reference controls exist
        if not hasattr(self, 'ref_previews'):
            self._build_reference_controls()

        # Update preview & panel sizes to 16:9 while keeping width
        for i in range(4):
            try:
                if hasattr(self.ref_previews[i], 'Size'):
                    self.ref_previews[i].Size = Drawing.Size(img_w, img_h)
                if hasattr(self.ref_preview_panels[i], 'Size'):
                    self.ref_preview_panels[i].Size = Drawing.Size(img_w, img_h + 6)  # + padding
                    self.ref_preview_panels[i].Padding = Drawing.Padding(3)
                    self.ref_preview_panels[i].Text = ""
            except Exception:
                pass

        # Build a 4×2 table
        mood_table = Forms.TableLayout()
        mood_table.Spacing = Drawing.Size(col_gap, 6)

        # Row 1: images
        row1_cells = []
        for i in range(4):
            row1_cells.append(Forms.TableCell(self.ref_preview_panels[i], True))
        mood_table.Rows.Add(Forms.TableRow(*row1_cells))

        # Row 2: buttons (equal length, 30px height) - FIXED HEIGHT
        row2_cells = []
        for i in range(4):
            file_btn = self.ref_file_btns[i]
            clear_btn = self.ref_clear_btns[i]

            half_w = int((col_w - 6) / 2)  # Account for spacing between buttons
            
            # Set exact button dimensions
            for b in (file_btn, clear_btn):
                try:
                    b.Size = Drawing.Size(half_w, 30)
                    b.MinimumSize = Drawing.Size(half_w, 30)
                    b.MaximumSize = Drawing.Size(half_w, 30)
                except Exception:
                    pass
            
            # Create button row with fixed height container
            btn_container = Forms.DynamicLayout()
            btn_container.DefaultSpacing = Drawing.Size(6, 0)
            btn_container.AddRow(file_btn, clear_btn)
            
            # Wrap in a panel with fixed height to prevent expansion
            btn_panel = Forms.Panel()
            btn_panel.Content = btn_container
            btn_panel.Height = 30
            btn_panel.MinimumSize = Drawing.Size(-1, 30)
            btn_panel.MaximumSize = Drawing.Size(-1, 30)
            
            row2_cells.append(Forms.TableCell(btn_panel, False))

        mood_table.Rows.Add(Forms.TableRow(*row2_cells))

        layout.Add(mood_table)
        
        # 5. TIMER SECTION
        layout.AddRow(self._create_separator())
        
        timer_section = Forms.DynamicLayout()
        timer_section.DefaultSpacing = Drawing.Size(0, 8)
        timer_section.AddRow(self.timer_label)
        layout.Add(timer_section)
        
        return layout

    def _create_log_tab(self):
        """Create the Prompt Log tab content."""
        layout = Forms.DynamicLayout()
        layout.DefaultSpacing = Drawing.Size(10, 15)
        layout.Padding = Drawing.Padding(16)
        
        layout.AddRow(self.chat_log_tb)
        
        return layout

    def _create_setup_tab(self):
        """Create the Setup tab content."""
        layout = Forms.DynamicLayout()
        layout.DefaultSpacing = Drawing.Size(10, 20)
        layout.Padding = Drawing.Padding(16)
        
        # 1. API Key Section
        api_section = Forms.DynamicLayout()
        api_section.DefaultSpacing = Drawing.Size(0, 10)
        api_section.AddRow(self._create_label("Google Gemini API Key:"))
        api_table = Forms.TableLayout()
        api_table.Spacing = Drawing.Size(10, 0)
        api_table.Rows.Add(Forms.TableRow(
            Forms.TableCell(self.api_key_tb, True),
            Forms.TableCell(self.save_api_key_cb, False)
        ))
        api_section.Add(api_table)
        layout.Add(api_section)
        
        # API Key instructions
        api_help = Forms.Label()
        api_help.Text = "Get your API key at:\nhttps://aistudio.google.com"
        api_help.TextAlignment = TextAlignment.Left
        api_help.TextColor = Drawing.Colors.Gray
        layout.AddRow(api_help)

        layout.AddRow(self._create_separator())

        # 2. Output Folder Section
        folder_section = Forms.DynamicLayout()
        folder_section.DefaultSpacing = Drawing.Size(0, 10)
        folder_section.AddRow(self._create_label("Output Folder:"))
        folder_table = Forms.TableLayout()
        folder_table.Spacing = Drawing.Size(10, 0)
        folder_table.Rows.Add(Forms.TableRow(
            Forms.TableCell(self.output_folder_tb, True),
            Forms.TableCell(self.browse_folder_btn, False)
        ))
        folder_section.Add(folder_table)
        layout.Add(folder_section)
        
        layout.AddRow(None)  # Spacer
        return layout

    def _create_about_tab(self):
        """Create the About tab content."""
        layout = Forms.DynamicLayout()
        layout.DefaultSpacing = Drawing.Size(10, 15)
        layout.Padding = Drawing.Padding(30)
        
        layout.AddRow(None)  # Spacer
        layout.AddRow(None)  # Spacer
        layout.AddRow(None)  # Spacer
        layout.AddRow(None)  # Spacer
        layout.AddRow(None)  # Spacer

        # Title
        title = Forms.Label()
        title.Text = "Nano 🍌 Viewport Renderer-er 2.0"
        title.Font = Drawing.Fonts.Sans(20, Drawing.FontStyle.Bold)
        title.TextAlignment = TextAlignment.Center
        layout.AddRow(title)

        layout.AddRow(None)  # Spacer

        # Description
        description = Forms.Label()
        description.Text = """AI-powered viewport rendering for Rhino 8 
using Google Gemini 2.5 Flash Image (aka Nano Banana)."""
        description.Font = Drawing.Fonts.Sans(16)
        description.TextAlignment = TextAlignment.Center
        layout.AddRow(description)

        layout.AddRow(None)  # Spacer

        
        layout.AddRow(self._create_separator())
        layout.AddRow(None)  # Spacer

        # Designer Info
        designer_title = Forms.Label()
        designer_title.Text = "Designer / Developer"
        designer_title.Font = Drawing.Fonts.Sans(20, Drawing.FontStyle.Bold)
        designer_title.TextAlignment = TextAlignment.Center
        layout.AddRow(designer_title)
        
        designer_name = Forms.Label()
        designer_name.Text = "S. Dogan Sekercioglu"
        designer_name.Font = Drawing.Fonts.Sans(16)
        designer_name.TextAlignment = TextAlignment.Center
        layout.AddRow(designer_name)
        
        layout.AddRow(None)  # Spacer

        layout.AddRow(self._create_separator())
        
        layout.AddRow(None)  # Spacer

        # Technology Stack
        tech_title = Forms.Label()
        tech_title.Text = "Powered By"
        tech_title.Font = Drawing.Fonts.Sans(20, Drawing.FontStyle.Bold)
        tech_title.TextAlignment = TextAlignment.Center
        layout.AddRow(tech_title)
        
        tech_list = Forms.Label()
        tech_list.Text = """McNeel Rhino 8
Google Gemini 2.5 Flash Image
Anthropic Claude
        """
        tech_list.TextColor = Drawing.Colors.Gray
        tech_list.TextAlignment = TextAlignment.Center
        layout.AddRow(tech_list)
        
        layout.AddRow(None)  # Spacer
        
        # Footer
        footer = Forms.Label()
        footer.Text = "© 2025 S. Dogan Sekercioglu | www.dogansekercioglu.com\nNot affiliated with Robert McNeel & Associates, Google LLC or Anthropic"
        footer.TextAlignment = TextAlignment.Center
        footer.TextColor = Drawing.Colors.Gray
        footer.Font = Drawing.Fonts.Sans(10)
        layout.AddRow(footer)
        return layout

    def _select_reference_image(self, index):
        """Handle mood board image selection."""
        try:
            file_dialog = Forms.OpenFileDialog()
            file_dialog.Title = f"Choose mood board image #{index + 1}"
            try:
                image_filter = Forms.FileDialogFilter("Images", ".png", ".jpg", ".jpeg", ".webp", ".bmp")
                file_dialog.Filters.Add(image_filter)
            except Exception:
                pass
            
            if file_dialog.ShowDialog(self) == Forms.DialogResult.Ok:
                file_path = file_dialog.FileName
                self._load_reference_preview(index, file_path)
        except Exception as e:
            self._append_chat_log(f"Failed to select mood board image #{index + 1}: {e}")

    def _clear_reference_image(self, index):
        """Clear a mood board image."""
        self.ref_previews[index].Image = None
        # Also remove the stored file path so it won't be included in API requests
        if hasattr(self.ref_previews[index], '_file_path'):
            delattr(self.ref_previews[index], '_file_path')

    def _load_reference_preview(self, index, file_path):
        """Load mood board image preview."""
        try:
            if file_path and Path(file_path).exists():
                eto_bitmap = Drawing.Bitmap(file_path)
                self.ref_previews[index].Image = eto_bitmap
                # Store file path for later use
                setattr(self.ref_previews[index], '_file_path', file_path)
        except Exception as e:
            self._append_chat_log(f"Failed to load mood board preview #{index + 1}: {e}")

    def on_browse_folder(self, sender, event):
        """Handle browse folder button click using SelectFolderDialog."""
        try:
            folder_dialog = Forms.SelectFolderDialog()
            folder_dialog.Directory = self.output_folder_tb.Text
            folder_dialog.Title = "Select Output Folder for Generated Images"
            
            if folder_dialog.ShowDialog(self) == Forms.DialogResult.Ok:
                self.output_folder_tb.Text = folder_dialog.Directory
        except Exception as e:
            self._append_chat_log(f"Failed to open folder dialog: {e}")

    def _open_folder(self, folder_path):
        """Open the folder in Finder/Explorer."""
        try:
            import subprocess
            import sys
            
            if sys.platform == "darwin":  # macOS
                subprocess.run(["open", str(folder_path)])
            elif sys.platform == "win32":  # Windows
                subprocess.run(["explorer", str(folder_path)])
            else:  # Linux
                subprocess.run(["xdg-open", str(folder_path)])
        except Exception as e:
            self._append_chat_log(f"Failed to open folder: {e}")

    def _update_viewport_preview(self, bitmap):
        """Update viewport preview with captured image."""
        try:
            if not bitmap or not self.viewport_preview:
                return
                
            # Use reliable file-based conversion method
            temp_dir = Path(self.output_folder_tb.Text)
            temp_dir.mkdir(exist_ok=True)
            temp_path = temp_dir / f"viewport_preview_{time.strftime('%H%M%S')}.png"
            
            # Save original bitmap to temp file
            bitmap.Save(str(temp_path), Imaging.ImageFormat.Png)
            
            # Load as Eto bitmap
            eto_bitmap = Drawing.Bitmap(str(temp_path))
            self.viewport_preview.Image = eto_bitmap
            
            # Clean up temp file
            try:
                temp_path.unlink()
            except Exception:
                pass
                    
        except Exception as e:
            pass

    def _format_camera_info_for_prompt(self, camera_info):
        """Format camera information for inclusion in AI prompts."""
        if not camera_info:
            return ""
        
        # Build camera description for the AI
        camera_desc = []
        
        if camera_info.get('type') == 'perspective':
            camera_desc.append(f"Shot with a {camera_info.get('lens_length', 'unknown')} {camera_info.get('lens_type', 'lens')}")
            if camera_info.get('field_of_view'):
                camera_desc.append(f"field of view {camera_info.get('field_of_view')}")
        elif camera_info.get('type') == 'parallel':
            camera_desc.append("Shot with orthographic projection (no perspective distortion)")
        
        if camera_desc:
            return f"Camera settings: {', '.join(camera_desc)}. "
        return ""

    def _append_chat_log(self, message, user_input=False, ai_response=False):
        """Append message to chat log with Prompt formatting."""
        timestamp = time.strftime("%H:%M:%S")
        
        if user_input:
            # User input formatting
            self.chat_log_tb.Text += f"\n[{timestamp}] You: {message}\n"
        elif ai_response:
            # AI response formatting
            self.chat_log_tb.Text += f"[{timestamp}] Nano 🍌: {message}\n"
        else:
            # System message formatting
            self.chat_log_tb.Text += f"[{timestamp}] System: {message}\n"
        
        # Auto-scroll to bottom
        self.chat_log_tb.CaretIndex = len(self.chat_log_tb.Text)

    def _update_status_bar(self):
        """Update status bar with current session and total usage."""
        try:
            # Update session stats (cost only)
            self.status_session_label.Text = f"Session: ${self.session_cost:.2f}"
            
            # Update total stats from settings (cost only)
            total_cost = self.settings.get("total_cost", 0.0)
            self.status_total_label.Text = f"Total: ${total_cost:.2f}"
            
        except Exception as e:
            self._append_chat_log(f"Failed to update status bar: {e}")

    def _save_current_settings(self):
        """Save current form settings to JSON file."""
        try:
            # Don't save placeholder text
            prompt_text = "" if self._prompt_placeholder_active else self.prompt_tb.Text
            self.settings.update({
                "api_key": self.api_key_tb.Text,
                "output_folder": self.output_folder_tb.Text,
                "prompt": prompt_text
            })
            save_settings(self.settings)
        except Exception as e:
            self._append_chat_log(f"Failed to save settings: {e}")

    def _track_cumulative_usage(self, tokens, cost, show_session_cost=True):
        """Track cumulative usage across sessions and update status bar."""
        try:
            # Update session totals
            self.session_tokens += tokens
            self.session_cost += cost
            
            # Update settings with cumulative totals
            current_total_tokens = self.settings.get("total_tokens_used", 0)
            current_total_cost = self.settings.get("total_cost", 0.0)
            
            self.settings["total_tokens_used"] = current_total_tokens + tokens
            self.settings["total_cost"] = current_total_cost + cost
            self.settings["last_generation_date"] = time.strftime("%Y-%m-%d %H:%M:%S")
            
            save_settings(self.settings)
            
            # Update status bar display
            self._update_status_bar()
            
            if show_session_cost:
                self._append_chat_log(f"Session cost: ${self.session_cost:.4f}")
            
        except Exception as e:
            self._append_chat_log(f"Failed to track usage: {e}")

    def on_capture_viewport(self, sender, event):
        """Handle capture viewport button - AUTOMATICALLY PROCESSES WITH STRUCTURED PROMPT."""
        # Check if API key is entered
        api_key = self.api_key_tb.Text or os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            Forms.MessageBox.Show(
                self,
                "Please enter your Google Gemini API key under the Setup tab to start.",
                "API Key Required",
                Forms.MessageBoxButtons.OK,
                Forms.MessageBoxType.Warning
            )
            return
        
        # Show warning if this is not the first capture
        if not self._first_capture:
            result = Forms.MessageBox.Show(
                self,
                "Capturing a new viewport will reset your current iteration and purge conversation memory. Do you want to continue?",
                "Reset Iteration Warning",
                Forms.MessageBoxButtons.YesNo,
                Forms.MessageBoxType.Warning
            )
            
            if result == Forms.DialogResult.No:
                return  # User cancelled, exit early
            
            # Use a timer to delay execution and let dialog close
            import threading
            delay_timer = threading.Timer(0.5, self._execute_capture_viewport)
            delay_timer.start()
        else:
            # First capture, execute immediately
            self._execute_capture_viewport()
    
    def _execute_capture_viewport(self):
        """Execute the actual viewport capture and processing."""
        try:
            # Mark that we've done at least one capture
            self._first_capture = False
            
            # PURGE MEMORY AND START FRESH
            self.Prompt_history = []
            
            # Start timer for processing
            self._start_timer()
            
            # Get API key
            api_key = self.api_key_tb.Text or os.environ.get("GEMINI_API_KEY", "")
            if not api_key:
                self._append_chat_log("Error: Please enter your Google API key or set GEMINI_API_KEY environment variable.")
                self._stop_timer()
                return

            # Validate output folder
            output_dir = Path(self.output_folder_tb.Text)
            if not output_dir.exists():
                try:
                    output_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    self._append_chat_log(f"Error: Cannot create output directory: {e}")
                    self._stop_timer()
                    return
            
            # Capture viewport with clean background (curves hidden)
            bitmap, png_bytes, camera_info = capture_active_view_shaded()
            
            # Store the captured data
            self._last_viewport_bitmap = bitmap
            self._captured_viewport_bytes = png_bytes
            self._camera_info = camera_info
            self._viewport_captured = True
            
            # Log camera info to chat
            if camera_info.get('type') == 'parallel':
                camera_info_str = "Camera: orthographic"
            else:
                camera_info_str = f"Camera: {camera_info.get('type', 'unknown')}"
                if camera_info.get('lens_length') != 'N/A (parallel projection)':
                    camera_info_str += f", {camera_info.get('lens_length', 'unknown')} {camera_info.get('lens_type', 'lens')}"
                if camera_info.get('field_of_view'):
                    camera_info_str += f", FOV: {camera_info.get('field_of_view', 'unknown')}"
            self._append_chat_log(camera_info_str)
            
            # ENABLE PROMPT BOX NOW THAT VIEWPORT IS CAPTURED
            self._update_prompt_state()
            
            # IMMEDIATELY PROCESS WITH STRUCTURED PROMPT
            try:
                from google import genai
                from google.genai import types
            except ImportError as e:
                self._append_chat_log(f"Error: Failed to import google-genai: {e}")
                self._stop_timer()
                return

            # BUILD STRUCTURED PROMPT WITH CAMERA INFO
            camera_prompt_addition = self._format_camera_info_for_prompt(camera_info)
            structured_prompt = f"Place what you see in the 3D viewport capture in a photo studio with a soft infinite white background. Always use the same soft daylight-like illumination. {camera_prompt_addition}Compare your result with the reference image and do not release it until the result is a complete match. Do not modify or change anything that doesn't match the viewport image in any way."
            
            # Log the structured prompt to chat
            self._append_chat_log(structured_prompt, user_input=True)
            
            # Build content parts - CAPTURE VIEW IGNORES MOOD BOARD
            parts = []
            parts.append(types.Part.from_text(text=structured_prompt))
            parts.append(types.Part.from_bytes(data=png_bytes, mime_type="image/png"))
            
            # NOTE: Mood board images are NOT included during Capture View
            # They are only used during Generate operations

            contents = [types.Content(role="user", parts=parts)]

            # Store initial Prompt in history
            self.Prompt_history = contents.copy()
            
            # Call Gemini API with structured prompt
            client = genai.Client(api_key=api_key)
            config = types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"])
            
            response = client.models.generate_content(
                model=self.model, 
                contents=contents, 
                config=config
            )
            
            # Process response and show result
            self._process_response(response, output_dir, is_viewport_processing=True, show_usage=False)
            
            # Enable both generate and iterate buttons
            self.generate_btn.Enabled = True
            self.iterate_btn.Enabled = True
            
            # Stop timer
            self._stop_timer()
            
        except Exception as e:
            self._append_chat_log(f"Failed to capture and process viewport: {e}")
            self._stop_timer()

    def on_generate(self, sender, event):
        """Handle generate button - UNRESTRICTED GENERATION."""
        # Check if viewport captured
        if not self._viewport_captured or not self._captured_viewport_bytes:
            self._append_chat_log("Please capture viewport first!")
            return
        
        # Check if API key is entered
        api_key = self.api_key_tb.Text or os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            Forms.MessageBox.Show(
                self,
                "Please enter your Google Gemini API key under the Setup tab to start.",
                "API Key Required",
                Forms.MessageBoxButtons.OK,
                Forms.MessageBoxType.Warning
            )
            return
        
        # Start timer
        self._start_timer()
        
        # Save current settings first
        self._save_current_settings()
        
        # Get user prompt
        user_prompt = self.prompt_tb.Text.strip() if self.prompt_tb.Text and not self._prompt_placeholder_active else ""
        has_user_input = bool(user_prompt)
        
        # Build the full prompt that will be sent
        strict_instruction = "Follow the primary reference image strictly. Do not change the camera angle, form, or composition. "
        if has_user_input:
            full_prompt = strict_instruction + user_prompt
        else:
            full_prompt = strict_instruction + "Create an image based on this reference."
        
        # Log the full prompt to chat
        self._append_chat_log(full_prompt, user_input=True)
        
        # Validate output folder
        output_dir = Path(self.output_folder_tb.Text)
        if not output_dir.exists():
            try:
                output_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self._append_chat_log(f"Error: Cannot create output directory: {e}")
                self._stop_timer()
                return

        # IMPORT GEMINI API
        try:
            from google import genai
            from google.genai import types
        except ImportError as e:
            self._append_chat_log(f"Error: Failed to import google-genai: {e}")
            self._stop_timer()
            return

        # BUILD SIMPLE, UNRESTRICTED CONTENT PARTS
        parts = []
        
        # 1. Add the Primary Reference image FIRST
        parts.append(types.Part.from_bytes(data=self._captured_viewport_bytes, mime_type="image/png"))
        
        # 2. Add the full prompt (already built with strict instruction)
        parts.append(types.Part.from_text(text=full_prompt))
        
        # 3. Add mood board images for styling inspiration LAST
        for i, preview in enumerate(self.ref_previews):
            file_path = getattr(preview, '_file_path', None)
            if file_path:
                part = read_file_as_part(file_path)
                if part is not None:
                    parts.append(part)

        contents = [types.Content(role="user", parts=parts)]

        # CALL GEMINI API
        try:
            # Get API key (already validated at the start)
            api_key = self.api_key_tb.Text or os.environ.get("GEMINI_API_KEY", "")
            client = genai.Client(api_key=api_key)
            
            # Determine if this is a fresh Prompt or iteration
            is_iteration = len(self.Prompt_history) > 0
            
            if is_iteration:
                # ITERATION: Use Prompt history for context
                # Add the new user input to Prompt history with proper order
                current_request_parts = []
                
                # 1. Primary Reference first
                current_request_parts.append(types.Part.from_bytes(data=self._captured_viewport_bytes, mime_type="image/png"))
                
                # 2. Strict instruction + prompt
                strict_instruction = "Follow the primary reference image strictly. Do not change the camera angle, form, or composition. "
                if has_user_input:
                    iteration_prompt = strict_instruction + user_prompt
                else:
                    iteration_prompt = strict_instruction + "Continue with this image"
                current_request_parts.append(types.Part.from_text(text=iteration_prompt))
                
                # 3. Mood board images last
                for i, preview in enumerate(self.ref_previews):
                    file_path = getattr(preview, '_file_path', None)
                    if file_path:
                        part = read_file_as_part(file_path)
                        if part is not None:
                            current_request_parts.append(part)
                
                # Add new user message to Prompt history
                self.Prompt_history.append(types.Content(role="user", parts=current_request_parts))
                
                # Use full prompt history for API call
                contents = self.Prompt_history
                
                # Use simple config for iterations to maintain Prompt flow
                config = types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"])
                
            else:
                # FRESH Prompt: Simple unrestricted generation
                # Use simple config
                config = types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"])
                
                # Use the constructed parts for fresh Prompt (already built above)
                contents = [types.Content(role="user", parts=parts)]
                
                # Store initial Prompt in history
                self.Prompt_history = contents.copy()
                
            response = client.models.generate_content(
                model=self.model, 
                contents=contents, 
                config=config
            )
        except Exception as e:
            self._append_chat_log(f"API error: {e}")
            self._stop_timer()
            return

        # EXTRACT AND SAVE IMAGE
        self._process_response(response, output_dir, show_usage=False)
        
        # Enable iterate button
        self.iterate_btn.Enabled = True
        
        # Stop timer
        self._stop_timer()

    def on_iterate(self, sender, event):
        """Handle iterate button - STEP 3 of chat workflow."""
        if not self._last_generated_image_path or not Path(self._last_generated_image_path).exists():
            self._append_chat_log("No generated image available to iterate with!")
            return
        
        try:
            # KEEP CONTEXT AND CHAT MEMORY - DO NOT CLEAR Prompt_history
            
            # Replace the Primary Reference with the generated result
            # Load the generated image as the new Primary Reference
            generated_bitmap = SD.Bitmap(str(self._last_generated_image_path))
            generated_png_bytes = bitmap_to_png_bytes(generated_bitmap)
            
            # Update the Primary Reference data
            self._last_viewport_bitmap = generated_bitmap
            self._captured_viewport_bytes = generated_png_bytes
            
            # Update the Primary Reference preview
            self._update_viewport_preview(generated_bitmap)
            
            # Clear the generated result preview
            self.result_preview.Image = None
            
            # Clear the prompt for next iteration
            if not self._prompt_ever_focused:
                self.prompt_tb.Text = self._prompt_placeholder_text
                self.prompt_tb.TextColor = Drawing.Colors.Gray
                self._prompt_placeholder_active = True
            else:
                self.prompt_tb.Text = ""
                self._prompt_placeholder_active = False
            
            # Reset some state for next round
            self.iterate_btn.Enabled = False  # Disable until next generation
            
            # Keep viewport_captured = True since we now have a valid reference
            self._viewport_captured = True
            
        except Exception as e:
            self._append_chat_log(f"Failed to iterate: {e}")

    def on_show_generated(self, sender, event):
        """Handle show generated image button."""
        if not self._last_generated_image_path or not Path(self._last_generated_image_path).exists():
            self._append_chat_log("Error: No generated image available to show.")
            return
            
        try:
            sys_bitmap = SD.Bitmap(str(self._last_generated_image_path))
            ms = System.IO.MemoryStream()
            sys_bitmap.Save(ms, Imaging.ImageFormat.Png)
            ms.Position = 0
            eto_bitmap = Drawing.Bitmap(ms)
            
            # Get dimensions for sizing
            img_width = sys_bitmap.Width
            img_height = sys_bitmap.Height
            
            # Create viewer dialog
            viewer = Forms.Dialog()
            viewer.Title = f"Generated Image: {Path(self._last_generated_image_path).name}"
            
            # Size the dialog (limit max size)
            max_width = 1024
            max_height = 1024
            if img_width > max_width or img_height > max_height:
                scale = min(max_width / img_width, max_height / img_height)
                display_width = int(img_width * scale)
                display_height = int(img_height * scale)
            else:
                display_width = img_width
                display_height = img_height
                
            viewer.Size = Drawing.Size(display_width + 40, display_height + 120)
            viewer.Padding = Drawing.Padding(20)
            
            # Create image view with the loaded bitmap
            image_view = Forms.ImageView()
            image_view.Size = Drawing.Size(display_width, display_height)
            image_view.Image = eto_bitmap
            
            # Action buttons
            open_folder_btn = Forms.Button()
            open_folder_btn.Text = "Open Folder"
            open_folder_btn.Size = Drawing.Size(150, 35)
            open_folder_btn.Click += lambda s, e: self._open_folder(Path(self._last_generated_image_path).parent)
            
            close_btn = Forms.Button()
            close_btn.Text = "Close"
            close_btn.Size = Drawing.Size(150, 35)
            close_btn.Click += lambda s, e: viewer.Close()
            
            # Layout
            layout = Forms.DynamicLayout()
            layout.DefaultSpacing = Drawing.Size(8, 8)
            layout.Add(image_view)
            
            # Button row with equally sized buttons
            button_layout = Forms.DynamicLayout()
            button_layout.DefaultSpacing = Drawing.Size(15, 8)
            button_layout.AddRow(open_folder_btn, Forms.Label(), close_btn)
            layout.Add(button_layout)
            
            viewer.Content = layout
            viewer.ShowModal(self)
            
        except Exception as e:
            self._append_chat_log(f"Failed to show image: {e}")
            self._open_folder(Path(self._last_generated_image_path).parent)

    def _process_response(self, response, output_dir, is_viewport_processing=False, show_usage=True):
        """Process the Gemini API response and extract image + usage info."""
        try:
            # Extract usage information first
            usage_info = getattr(response, 'usage_metadata', None)
            if usage_info:
                input_tokens = getattr(usage_info, 'prompt_token_count', 0)
                output_tokens = getattr(usage_info, 'candidates_token_count', 0) 
                total_tokens = getattr(usage_info, 'total_token_count', 0)
                
                if show_usage:
                    self._append_chat_log(f"Usage: {input_tokens} input + {output_tokens} output = {total_tokens} tokens")
                
                # Calculate cost using updated pricing framework
                cost_info = self._calculate_generation_cost(input_tokens, output_tokens)
                
                if show_usage:
                    self._append_chat_log(f"Cost: ${cost_info['total_cost']:.4f} (${cost_info['input_cost']:.4f} input + ${cost_info['output_cost']:.4f} output + ${cost_info['image_cost']:.4f} image)")
                
                # Use total_cost for tracking
                total_cost = cost_info['total_cost']
            else:
                # Fallback if no usage metadata available - estimate based on image generation only
                pricing = self._get_model_pricing()
                total_cost = pricing["cost_per_image"]
                total_tokens = pricing["tokens_per_image"]
                if show_usage:
                    self._append_chat_log(f"Usage metadata unavailable - estimated cost: ${total_cost:.4f} (image generation only)")
            
            img_bytes = None
            img_mime = "image/png"
            analysis_text = None
            
            # Walk parts for both image data and text analysis
            for candidate in getattr(response, "candidates", []) or []:
                content = getattr(candidate, "content", None)
                if not content:
                    continue
                    
                for i, part in enumerate(content.parts):
                    # Check for image data
                    inline_data = getattr(part, "inline_data", None) or getattr(part, "inlineData", None)
                    if inline_data and getattr(inline_data, "data", None):
                        img_bytes = bytes(inline_data.data)
                        img_mime = getattr(inline_data, "mime_type", None) or getattr(inline_data, "mimeType", None) or img_mime
                    
                    # Check for text analysis
                    text_content = getattr(part, "text", None)
                    if text_content and text_content.strip():
                        # Only capture substantial text (not just whitespace or short responses)
                        if len(text_content.strip()) > 10:
                            analysis_text = text_content.strip()

            # Display Nano Banana's analysis if available
            if analysis_text:
                self._append_chat_log(analysis_text, ai_response=True)
            else:
                self._append_chat_log("Image generated successfully!", ai_response=True)

            # ADD AI RESPONSE TO Prompt HISTORY FOR MEMORY
            try:
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'content'):
                        # Add the complete AI response to Prompt history
                        self.Prompt_history.append(candidate.content)
            except Exception as e:
                if show_usage:
                    self._append_chat_log(f"Warning: Failed to store response in memory: {e}")

            # Fallback: try to parse base64 from text response if no image found yet
            if not img_bytes:
                for candidate in getattr(response, "candidates", []) or []:
                    content = getattr(candidate, "content", None)
                    if not content:
                        continue
                        
                    for part in content.parts:
                        text_content = getattr(part, "text", None)
                        if text_content:
                            try:
                                data = text_content.strip()
                                if data.startswith("data:image"):
                                    b64_data = data.split(",", 1)[1]
                                    img_bytes = base64.b64decode(b64_data)
                                    break
                            except Exception:
                                pass
                                
                    if img_bytes:
                        break

            if not img_bytes:
                self._append_chat_log("Error: No image returned by the model.")
                return

            # Save image bytes directly to selected output folder
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            if is_viewport_processing:
                output_path = output_dir / f"nano_banana_viewport_{timestamp}.png"
            else:
                output_path = output_dir / f"nano_banana_chat_{timestamp}.png"
            
            # Write bytes directly to file
            with open(output_path, "wb") as f:
                f.write(img_bytes)

            # Store for later viewing  
            self._last_generated_image_path = str(output_path)
            self.show_generated_btn.Enabled = True

            # Update preview thumbnails based on operation type
            try:
                sys_bitmap = SD.Bitmap(str(output_path))
                ms = System.IO.MemoryStream()
                sys_bitmap.Save(ms, Imaging.ImageFormat.Png)
                ms.Position = 0
                eto_bitmap = Drawing.Bitmap(ms)
                
                if is_viewport_processing:
                    # Show processed viewport result in Primary Reference panel
                    self.viewport_preview.Image = eto_bitmap
                    # Also update the internal reference data for iterations
                    self._last_viewport_bitmap = sys_bitmap
                    self._captured_viewport_bytes = img_bytes
                else:
                    # Show generation result in Generated Result panel
                    self.result_preview.Image = eto_bitmap
                    
            except Exception:
                try:
                    with open(output_path, 'rb') as f:
                        img_bytes_reload = f.read()
                    byte_stream = System.IO.MemoryStream(img_bytes_reload)
                    eto_bitmap = Drawing.Bitmap(byte_stream)
                    
                    if is_viewport_processing:
                        self.viewport_preview.Image = eto_bitmap
                        self._captured_viewport_bytes = img_bytes_reload
                    else:
                        self.result_preview.Image = eto_bitmap
                except Exception:
                    if is_viewport_processing:
                        self.viewport_preview.Image = None
                    else:
                        self.result_preview.Image = None
            
            # Save usage info to settings for cumulative tracking
            if usage_info and total_tokens > 0:
                self._track_cumulative_usage(total_tokens, total_cost, show_session_cost=show_usage)
            elif 'total_cost' in locals():
                # Track cost even without detailed token usage
                self._track_cumulative_usage(0, total_cost, show_session_cost=show_usage)
            
        except Exception as e:
            self._append_chat_log(f"Failed to process response: {e}")


def show_chat_ui():
    """Show the chat UI dialog."""
    dialog = NanoBananaChatForm()
    dialog.Show()


if __name__ == "__main__":
    show_chat_ui()