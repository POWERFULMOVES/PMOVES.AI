import { Sandbox } from "@e2b/desktop";
import {
  MAX_RESOLUTION_WIDTH,
  MAX_RESOLUTION_HEIGHT,
  MIN_RESOLUTION_WIDTH,
  MIN_RESOLUTION_HEIGHT,
} from "@/lib/config";
import sharp from "sharp";

/**
 * ResolutionScaler handles resolution scaling between the original desktop
 * resolution and the scaled model resolution, including coordinate transformations
 * and screenshot scaling.
 *
 * This class maintains aspect ratio consistency while ensuring the resolution
 * stays within configured boundaries, providing accurate coordinate mapping
 * between different resolution spaces.
 */
export class ResolutionScaler {
  // Private properties
  private desktop: Sandbox;
  private originalResolution: [number, number];
  private scaledResolution: [number, number];
  private scaleFactor: number;
  private originalAspectRatio: number;
  private scaledAspectRatio: number;

  /**
   * Creates a new ResolutionScaler
   *
   * @param desktop - The sandbox instance used for taking screenshots
   * @param originalResolution - The original desktop resolution [width, height]
   */
  constructor(desktop: Sandbox, originalResolution: [number, number]) {
    this.desktop = desktop;
    this.originalResolution = originalResolution;
    this.originalAspectRatio = originalResolution[0] / originalResolution[1];

    // Calculate scaled resolution and scale factor immediately on instantiation
    const { scaledResolution, scaleFactor } =
      this.calculateScaledResolution(originalResolution);
    this.scaledResolution = scaledResolution;
    this.scaleFactor = scaleFactor;
    this.scaledAspectRatio = scaledResolution[0] / scaledResolution[1];

    // Validate coordinate scaling accuracy
    this.validateCoordinateScaling();
  }

  /**
   * Get the original desktop resolution
   *
   * @returns The original resolution as [width, height]
   */
  public getOriginalResolution(): [number, number] {
    return this.originalResolution;
  }

  /**
   * Get the scaled resolution used for model interactions
   *
   * @returns The scaled resolution as [width, height]
   */
  public getScaledResolution(): [number, number] {
    return this.scaledResolution;
  }

  /**
   * Get the scale factor between original and scaled resolutions
   *
   * @returns The scale factor
   */
  public getScaleFactor(): number {
    return this.scaleFactor;
  }

  /**
   * Get the aspect ratio of the original resolution
   *
   * @returns The original aspect ratio (width/height)
   */
  public getOriginalAspectRatio(): number {
    return this.originalAspectRatio;
  }

  /**
   * Get the aspect ratio of the scaled resolution
   *
   * @returns The scaled aspect ratio (width/height)
   */
  public getScaledAspectRatio(): number {
    return this.scaledAspectRatio;
  }

  /**
   * Validates coordinate scaling functions by performing round-trip tests
   * on several key positions across the screen
   */
  private validateCoordinateScaling(): void {
    // Test points at corners, center, and edges
    const testPoints: Array<{ name: string; point: [number, number] }> = [
      { name: "Top-left corner", point: [0, 0] },
      { name: "Top-right corner", point: [this.originalResolution[0] - 1, 0] },
      {
        name: "Bottom-left corner",
        point: [0, this.originalResolution[1] - 1],
      },
      {
        name: "Bottom-right corner",
        point: [this.originalResolution[0] - 1, this.originalResolution[1] - 1],
      },
      {
        name: "Center",
        point: [
          Math.floor(this.originalResolution[0] / 2),
          Math.floor(this.originalResolution[1] / 2),
        ],
      },
      { name: "Small target (10px)", point: [10, 10] }, // Small target test
    ];

    for (const { point } of testPoints) {
      this.testCoordinateRoundTrip(point);
    }
  }

  /**
   * Converts coordinates from model space to original desktop space.
   * Use this when the model sends coordinates (based on scaled screenshot)
   * that need to be converted to the original desktop space for actual interaction.
   *
   * @param coordinate - Coordinates in model's scaled space [x, y]
   * @returns Coordinates in original desktop space [x, y]
   */
  public scaleToOriginalSpace(coordinate: [number, number]): [number, number] {
    // Store the exact scaled values before rounding
    const exactScaledX = coordinate[0] / this.scaleFactor;
    const exactScaledY = coordinate[1] / this.scaleFactor;

    // Round only at the final step for pixel-perfect positioning
    const finalX = Math.round(exactScaledX);
    const finalY = Math.round(exactScaledY);

    return [finalX, finalY];
  }

  /**
   * Converts coordinates from original desktop space to model space.
   * Use this when desktop coordinates need to be represented in the model's scaled space.
   *
   * @param coordinate - Coordinates in original desktop space [x, y]
   * @returns Coordinates in model's scaled space [x, y]
   */
  public scaleToModelSpace(coordinate: [number, number]): [number, number] {
    // Store the exact scaled values before rounding
    const exactScaledX = coordinate[0] * this.scaleFactor;
    const exactScaledY = coordinate[1] * this.scaleFactor;

    // Round only at the final step for pixel-perfect representation
    const finalX = Math.round(exactScaledX);
    const finalY = Math.round(exactScaledY);

    return [finalX, finalY];
  }

  /**
   * Tests the round-trip accuracy of coordinate scaling.
   * Helps identify potential precision issues with coordinate transformations.
   *
   * @param originalCoordinate - A coordinate in original space to test
   * @returns Object containing the original, model space, and round-trip coordinates with error
   */
  public testCoordinateRoundTrip(originalCoordinate: [number, number]): {
    original: [number, number];
    modelSpace: [number, number];
    roundTrip: [number, number];
    error: [number, number];
  } {
    const modelSpace = this.scaleToModelSpace(originalCoordinate);
    const roundTrip = this.scaleToOriginalSpace(modelSpace);

    const error: [number, number] = [
      roundTrip[0] - originalCoordinate[0],
      roundTrip[1] - originalCoordinate[1],
    ];

    return { original: originalCoordinate, modelSpace, roundTrip, error };
  }

  /**
   * Takes a screenshot at the scaled resolution suitable for model consumption.
   * The screenshot is automatically scaled to the target resolution while
   * preserving aspect ratio.
   *
   * @returns A buffer containing the scaled screenshot
   */
  public async takeScreenshot(): Promise<Buffer> {
    // Take the original screenshot
    const originalScreenshot = await this.desktop.screenshot();

    // If no scaling is needed, return the original
    if (this.scaleFactor === 1) {
      return Buffer.from(originalScreenshot);
    }

    // Scale the screenshot - use high quality settings for better small target visibility
    const scaledScreenshot = await this.scaleScreenshot(
      originalScreenshot,
      this.scaledResolution
    );

    return scaledScreenshot;
  }

  /**
   * Calculates a scaled resolution that maintains aspect ratio and fits within boundaries.
   * This ensures the resolution stays within MIN and MAX resolution constraints.
   *
   * @param originalResolution - The original resolution to scale
   * @returns The scaled resolution and scale factor
   */
  private calculateScaledResolution(originalResolution: [number, number]): {
    scaledResolution: [number, number];
    scaleFactor: number;
  } {
    const [width, height] = originalResolution;
    const originalAspectRatio = width / height;

    // If resolution is already within bounds, return it as is
    if (
      width <= MAX_RESOLUTION_WIDTH &&
      width >= MIN_RESOLUTION_WIDTH &&
      height <= MAX_RESOLUTION_HEIGHT &&
      height >= MIN_RESOLUTION_HEIGHT
    ) {
      return {
        scaledResolution: [width, height],
        scaleFactor: 1,
      };
    }

    // Calculate scale factors for width and height
    let widthScaleFactor = 1;
    if (width > MAX_RESOLUTION_WIDTH) {
      widthScaleFactor = MAX_RESOLUTION_WIDTH / width;
    } else if (width < MIN_RESOLUTION_WIDTH) {
      widthScaleFactor = MIN_RESOLUTION_WIDTH / width;
    }

    let heightScaleFactor = 1;
    if (height > MAX_RESOLUTION_HEIGHT) {
      heightScaleFactor = MAX_RESOLUTION_HEIGHT / height;
    } else if (height < MIN_RESOLUTION_HEIGHT) {
      heightScaleFactor = MIN_RESOLUTION_HEIGHT / height;
    }

    // Use the appropriate scale factor to ensure both dimensions are within bounds
    let scaleFactor;
    if (widthScaleFactor < 1 || heightScaleFactor < 1) {
      // We need to scale down, use the smaller factor
      scaleFactor = Math.min(widthScaleFactor, heightScaleFactor);
    } else {
      // We need to scale up, use the larger factor
      scaleFactor = Math.max(widthScaleFactor, heightScaleFactor);
    }

    // Calculate new dimensions - store exact values before rounding
    const exactScaledWidth = width * scaleFactor;
    const exactScaledHeight = height * scaleFactor;

    // Round to integer pixels at the final step
    const scaledWidth = Math.round(exactScaledWidth);
    const scaledHeight = Math.round(exactScaledHeight);

    // Recalculate the final scale factor based on the rounded dimensions
    // This ensures more accurate coordinate scaling when using these dimensions
    const finalWidthScaleFactor = scaledWidth / width;
    const finalHeightScaleFactor = scaledHeight / height;

    // Using geometric mean for scale factor to better preserve aspect ratio
    const finalScaleFactor = Math.sqrt(
      finalWidthScaleFactor * finalHeightScaleFactor
    );

    return {
      scaledResolution: [scaledWidth, scaledHeight],
      scaleFactor: finalScaleFactor,
    };
  }

  /**
   * Scales a screenshot to the specified resolution.
   * Uses high-quality scaling to preserve UI details.
   *
   * @param screenshot - The original screenshot buffer
   * @param targetResolution - The target resolution to scale to [width, height]
   * @returns A buffer containing the scaled screenshot
   */
  private async scaleScreenshot(
    screenshot: Buffer | Uint8Array,
    targetResolution: [number, number]
  ): Promise<Buffer> {
    const [width, height] = targetResolution;

    try {
      // Use higher quality settings to preserve small UI elements better
      const result = await sharp(screenshot)
        .resize(width, height, {
          fit: "fill",
          kernel: "lanczos3", // Higher quality resampling kernel
          fastShrinkOnLoad: false, // Disable fast shrink for higher quality
        })
        .toBuffer();

      return result;
    } catch (error) {
      // Return original if scaling fails, ensuring it's a Buffer
      return Buffer.from(screenshot);
    }
  }
}
