/**
 * Video Object Tracking Service
 * Handles real-time object tracking using SAM2 video predictor
 */

interface TrackingMask {
  mask: number[][];  // 2D boolean array
  box: [number, number, number, number];  // [x1, y1, x2, y2]
  confidence: number;
}

interface TrackingFrame {
  object_name: string;
  masks: TrackingMask[];
}

class VideoTracker {
  private trackingId: string | null = null;
  private isTracking: boolean = false;
  private animationFrameId: number | null = null;
  private canvas: HTMLCanvasElement | null = null;
  private ctx: CanvasRenderingContext2D | null = null;
  private videoElement: HTMLVideoElement | null = null;

  /**
   * Start tracking an object in the video feed
   */
  async startTracking(
    objectName: string,
    initialBox: [number, number, number, number],
    canvas: HTMLCanvasElement,
    video: HTMLVideoElement
  ): Promise<string> {
    // Stop any existing tracking
    this.stopTracking();

    this.canvas = canvas;
    this.videoElement = video;
    this.ctx = canvas.getContext('2d');
    this.trackingId = `track_${Date.now()}`;
    this.isTracking = true;

    // Set canvas size to match video display dimensions
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    console.log(`🎯 Started tracking: ${objectName}`);
    console.log(`📐 Canvas size: ${canvas.width}x${canvas.height}`);
    console.log(`📹 Video size: ${video.videoWidth}x${video.videoHeight}`);
    console.log(`📦 Initial box (backend coords): [${initialBox.join(', ')}]`);

    // Scale box coordinates from video space to canvas display space
    const scaleX = canvas.width / video.videoWidth;
    const scaleY = canvas.height / video.videoHeight;

    const scaledBox: [number, number, number, number] = [
      initialBox[0] * scaleX,
      initialBox[1] * scaleY,
      initialBox[2] * scaleX,
      initialBox[3] * scaleY
    ];

    console.log(`📏 Scale factors: x=${scaleX.toFixed(2)}, y=${scaleY.toFixed(2)}`);
    console.log(`📦 Scaled box (canvas coords): [${scaledBox.map(v => v.toFixed(1)).join(', ')}]`);

    // Start the tracking loop
    this.trackingLoop(objectName, scaledBox);

    return this.trackingId;
  }

  /**
   * Main tracking loop - runs on every animation frame
   */
  private trackingLoop(objectName: string, box: [number, number, number, number]) {
    if (!this.isTracking || !this.ctx || !this.canvas || !this.videoElement) {
      return;
    }

    // Clear canvas
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    // Draw bounding box
    this.drawBox(box, objectName);

    // Request next frame
    this.animationFrameId = requestAnimationFrame(() =>
      this.trackingLoop(objectName, box)
    );
  }

  /**
   * Draw a bounding box with label
   */
  private drawBox(box: [number, number, number, number], label: string) {
    if (!this.ctx || !this.canvas) return;

    const [x1, y1, x2, y2] = box;
    const width = x2 - x1;
    const height = y2 - y1;

    // Draw semi-transparent fill
    this.ctx.fillStyle = 'rgba(147, 51, 234, 0.2)';  // Purple
    this.ctx.fillRect(x1, y1, width, height);

    // Draw border
    this.ctx.strokeStyle = 'rgba(147, 51, 234, 0.9)';
    this.ctx.lineWidth = 3;
    this.ctx.strokeRect(x1, y1, width, height);

    // Draw label background
    this.ctx.fillStyle = 'rgba(147, 51, 234, 0.9)';
    const labelPadding = 4;
    const fontSize = 14;
    this.ctx.font = `${fontSize}px sans-serif`;
    const labelWidth = this.ctx.measureText(label).width + labelPadding * 2;
    const labelHeight = fontSize + labelPadding * 2;

    this.ctx.fillRect(x1, y1 - labelHeight, labelWidth, labelHeight);

    // Draw label text
    this.ctx.fillStyle = 'white';
    this.ctx.fillText(label, x1 + labelPadding, y1 - labelPadding);
  }

  /**
   * Stop tracking
   */
  stopTracking() {
    this.isTracking = false;

    if (this.animationFrameId !== null) {
      cancelAnimationFrame(this.animationFrameId);
      this.animationFrameId = null;
    }

    // Clear canvas
    if (this.ctx && this.canvas) {
      this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }

    console.log('🛑 Stopped tracking');
  }

  /**
   * Check if currently tracking
   */
  isCurrentlyTracking(): boolean {
    return this.isTracking;
  }
}

// Export a singleton instance
export const videoTracker = new VideoTracker();
