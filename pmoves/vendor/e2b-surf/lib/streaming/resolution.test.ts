import { ResolutionScaler } from "./resolution";

// Mock Sandbox class for testing
class MockSandbox {
  async screenshot() {
    return Buffer.from("mock-screenshot");
  }
}

/**
 * Test suite for ResolutionScaler to diagnose issues with small targets on large resolutions
 */
async function runResolutionScalerTests() {
  console.log("=== ResolutionScaler Test Suite ===\n");

  // Test a range of resolutions from small to very large
  const testResolutions: Array<{ name: string; resolution: [number, number] }> =
    [
      { name: "Standard HD", resolution: [1280, 720] },
      { name: "Full HD", resolution: [1920, 1080] },
      { name: "2K", resolution: [2560, 1440] },
      { name: "4K", resolution: [3840, 2160] },
      { name: "5K", resolution: [5120, 2880] },
      { name: "Ultrawide", resolution: [3440, 1440] },
      { name: "Very Large Custom", resolution: [7680, 4320] }, // 8K
    ];

  // Small targets at different locations (absolute pixels)
  const smallTargets: Array<{
    name: string;
    position: [number, number];
    size: number;
  }> = [
    { name: "10px button near corner", position: [10, 10], size: 10 },
    { name: "5px icon near corner", position: [5, 5], size: 5 },
    { name: "3px dot near corner", position: [3, 3], size: 3 },
    { name: "1px pixel near corner", position: [1, 1], size: 1 },
  ];

  // Small targets at relative positions
  const createRelativeTargets = (resolution: [number, number]) => {
    return [
      {
        name: "Small target at 1% position",
        position: [
          Math.round(resolution[0] * 0.01),
          Math.round(resolution[1] * 0.01),
        ],
        size: Math.max(
          1,
          Math.round(Math.min(resolution[0], resolution[1]) * 0.005)
        ),
      },
      {
        name: "Small target at 5% position",
        position: [
          Math.round(resolution[0] * 0.05),
          Math.round(resolution[1] * 0.05),
        ],
        size: Math.max(
          1,
          Math.round(Math.min(resolution[0], resolution[1]) * 0.01)
        ),
      },
      {
        name: "Tiny target at center",
        position: [
          Math.round(resolution[0] * 0.5),
          Math.round(resolution[1] * 0.5),
        ],
        size: 3,
      },
    ];
  };

  // Run tests for each resolution
  for (const { name, resolution } of testResolutions) {
    console.log(
      `\n\n🔍 Testing ${name} resolution: ${resolution[0]}x${resolution[1]}`
    );

    // Create scaler with mock sandbox
    const mockSandbox = new MockSandbox() as any;
    const scaler = new ResolutionScaler(mockSandbox, resolution);

    // Log resolution details
    console.log(`Original: ${resolution[0]}x${resolution[1]}`);
    console.log(
      `Scaled: ${scaler.getScaledResolution()[0]}x${
        scaler.getScaledResolution()[1]
      }`
    );
    console.log(`Scale factor: ${scaler.getScaleFactor().toFixed(6)}`);

    // Test absolute small targets
    console.log("\n--- Testing Fixed Small Targets ---");
    testTargets(scaler, smallTargets);

    // Test relative small targets specific to this resolution
    console.log("\n--- Testing Relative Small Targets ---");
    testTargets(scaler, createRelativeTargets(resolution));

    // Test for systematic bias in rounding
    console.log("\n--- Testing for Systematic Rounding Bias ---");
    testRoundingBias(scaler);

    // Test a grid of points to look for patterns in errors
    console.log("\n--- Testing Coordinate Grid for Error Patterns ---");
    testCoordinateGrid(scaler);
  }

  // Special test case for the original reported issue
  console.log("\n\n🐞 Detailed Analysis of Small Target Edge Cases");
  testSmallTargetEdgeCases();
}

/**
 * Test a set of targets for coordinate mapping accuracy
 */
function testTargets(
  scaler: ResolutionScaler,
  targets: Array<{ name: string; position: [number, number]; size: number }>
) {
  for (const { name, position, size } of targets) {
    // Test center of target
    const result = scaler.testCoordinateRoundTrip(position);

    console.log(
      `\nTarget: ${name} at [${position[0]}, ${position[1]}] with size ${size}px`
    );

    // Calculate if the error would cause a miss
    const errorMagnitude = Math.sqrt(
      result.error[0] ** 2 + result.error[1] ** 2
    );
    const wouldMiss = errorMagnitude > size / 2;

    console.log(
      `  Model space: [${result.modelSpace[0]}, ${result.modelSpace[1]}]`
    );
    console.log(
      `  Round trip: [${result.roundTrip[0]}, ${result.roundTrip[1]}]`
    );
    console.log(
      `  Error: [${result.error[0]}, ${
        result.error[1]
      }] (${errorMagnitude.toFixed(2)} pixels)`
    );
    console.log(`  Would miss target? ${wouldMiss ? "❌ YES" : "✅ NO"}`);

    // Test all corners of the target to see if any part would be hit
    const corners = [
      [position[0] - size / 2, position[1] - size / 2],
      [position[0] + size / 2, position[1] - size / 2],
      [position[0] - size / 2, position[1] + size / 2],
      [position[0] + size / 2, position[1] + size / 2],
    ];

    let anyCornerHit = false;
    for (const corner of corners) {
      const cornerResult = scaler.testCoordinateRoundTrip([
        Math.round(corner[0]),
        Math.round(corner[1]),
      ]);
      const distance = Math.sqrt(
        (cornerResult.roundTrip[0] - position[0]) ** 2 +
          (cornerResult.roundTrip[1] - position[1]) ** 2
      );
      if (distance <= size / 2) {
        anyCornerHit = true;
        break;
      }
    }

    if (!anyCornerHit && wouldMiss) {
      console.log(`  ⚠️ CRITICAL: Target completely missed in mapping!`);
    }
  }
}

/**
 * Test for systematic rounding bias by checking many coordinate pairs
 */
function testRoundingBias(scaler: ResolutionScaler) {
  const original = scaler.getOriginalResolution();
  const samples = 100;

  const xErrors = [];
  const yErrors = [];

  // Generate random coordinates across the screen
  for (let i = 0; i < samples; i++) {
    const x = Math.floor(Math.random() * original[0]);
    const y = Math.floor(Math.random() * original[1]);

    const result = scaler.testCoordinateRoundTrip([x, y]);
    xErrors.push(result.error[0]);
    yErrors.push(result.error[1]);
  }

  // Calculate bias metrics
  const xAvgError = xErrors.reduce((sum, val) => sum + val, 0) / samples;
  const yAvgError = yErrors.reduce((sum, val) => sum + val, 0) / samples;

  const xAbsError =
    xErrors.reduce((sum, val) => sum + Math.abs(val), 0) / samples;
  const yAbsError =
    yErrors.reduce((sum, val) => sum + Math.abs(val), 0) / samples;

  console.log(
    `X bias: ${xAvgError.toFixed(4)} (avg error: ${xAbsError.toFixed(
      4
    )} pixels)`
  );
  console.log(
    `Y bias: ${yAvgError.toFixed(4)} (avg error: ${yAbsError.toFixed(
      4
    )} pixels)`
  );

  if (Math.abs(xAvgError) > 0.1 || Math.abs(yAvgError) > 0.1) {
    console.log(
      `  ⚠️ Significant systematic bias detected in coordinate mapping!`
    );
  }
}

/**
 * Test a grid of points to look for patterns in the errors
 */
function testCoordinateGrid(scaler: ResolutionScaler) {
  const original = scaler.getOriginalResolution();
  const gridSize = 10; // 10x10 grid

  let maxError = 0;
  let maxErrorLocation: [number, number] = [0, 0];

  // Sweep through grid points
  for (let xPercent = 0; xPercent <= 100; xPercent += 100 / gridSize) {
    for (let yPercent = 0; yPercent <= 100; yPercent += 100 / gridSize) {
      const x = Math.round((xPercent / 100) * (original[0] - 1));
      const y = Math.round((yPercent / 100) * (original[1] - 1));

      const result = scaler.testCoordinateRoundTrip([x, y]);
      const errorMagnitude = Math.sqrt(
        result.error[0] ** 2 + result.error[1] ** 2
      );

      if (errorMagnitude > maxError) {
        maxError = errorMagnitude;
        maxErrorLocation = [x, y];
      }
    }
  }

  console.log(
    `Maximum error: ${maxError.toFixed(2)} pixels at position [${
      maxErrorLocation[0]
    }, ${maxErrorLocation[1]}]`
  );

  // Test specific error patterns near edges
  console.log("\nTesting edge areas for increased errors:");

  // Test very near edges (first/last few pixels)
  const edgePoints = [
    [0, 0],
    [1, 0],
    [2, 0], // Top-left
    [original[0] - 1, 0],
    [original[0] - 2, 0], // Top-right
    [0, original[1] - 1],
    [0, original[1] - 2], // Bottom-left
    [original[0] - 1, original[1] - 1], // Bottom-right
  ];

  for (const point of edgePoints) {
    const result = scaler.testCoordinateRoundTrip(point);
    const errorMagnitude = Math.sqrt(
      result.error[0] ** 2 + result.error[1] ** 2
    );

    console.log(
      `Edge point [${point[0]}, ${point[1]}] error: ${errorMagnitude.toFixed(
        2
      )} pixels`
    );
  }
}

/**
 * Special test case focused on the edge case that might be causing the reported issue
 */
function testSmallTargetEdgeCases() {
  // Create a set of problematic scenarios to test
  const scenarios = [
    {
      name: "4K with tiny target",
      resolution: [3840, 2160],
      targets: [
        { name: "1px dot", position: [10, 10], size: 1 },
        { name: "2px dot", position: [20, 20], size: 2 },
        { name: "3px dot", position: [30, 30], size: 3 },
      ],
    },
    {
      name: "5K with sub-pixel rounding test",
      resolution: [5120, 2880],
      targets: Array.from({ length: 10 }, (_, i) => ({
        name: `Point ${i + 1}`,
        position: [i * 10 + 5, i * 10 + 5],
        size: 3,
      })),
    },
    {
      name: "Fractional scale factor test",
      resolution: [2560, 1600], // Likely to produce fractional scale factor
      targets: Array.from({ length: 10 }, (_, i) => ({
        name: `Point ${i + 1}`,
        position: [Math.floor((2560 * i) / 10), Math.floor((1600 * i) / 10)],
        size: 5,
      })),
    },
  ];

  // Run detailed test on each scenario
  for (const scenario of scenarios) {
    console.log(`\n=== ${scenario.name} ===`);
    const mockSandbox = new MockSandbox() as any;
    const scaler = new ResolutionScaler(mockSandbox, scenario.resolution);

    console.log(
      `Resolution: ${scenario.resolution[0]}x${scenario.resolution[1]}`
    );
    console.log(
      `Scaled to: ${scaler.getScaledResolution()[0]}x${
        scaler.getScaledResolution()[1]
      }`
    );
    console.log(`Scale factor: ${scaler.getScaleFactor().toFixed(6)}`);

    // Analyze exact vs. rounded scale factors
    const originalResolution = scenario.resolution;
    const scaledResolution = scaler.getScaledResolution();

    const exactXScaleFactor = scaledResolution[0] / originalResolution[0];
    const exactYScaleFactor = scaledResolution[1] / originalResolution[1];
    const actualScaleFactor = scaler.getScaleFactor();

    console.log(`\nExact X scale factor: ${exactXScaleFactor.toFixed(6)}`);
    console.log(`Exact Y scale factor: ${exactYScaleFactor.toFixed(6)}`);
    console.log(`Actual unified scale factor: ${actualScaleFactor.toFixed(6)}`);

    if (Math.abs(exactXScaleFactor - exactYScaleFactor) > 0.001) {
      console.log(
        `⚠️ Potential issue: X and Y scale factors differ significantly!`
      );
    }

    if (
      Math.abs(exactXScaleFactor - actualScaleFactor) > 0.001 ||
      Math.abs(exactYScaleFactor - actualScaleFactor) > 0.001
    ) {
      console.log(
        `⚠️ Potential issue: Actual scale factor differs from coordinate ratios!`
      );
    }

    // Detailed analysis of target accuracy with round-tripping
    console.log("\n--- Detailed Target Analysis ---");
    for (const target of scenario.targets) {
      const originalPoint = target.position;

      // Manual calculation to show exact math
      const manualToModelX = originalPoint[0] * actualScaleFactor;
      const manualToModelY = originalPoint[1] * actualScaleFactor;

      const roundedModelX = Math.round(manualToModelX);
      const roundedModelY = Math.round(manualToModelY);

      const manualBackToOriginalX = roundedModelX / actualScaleFactor;
      const manualBackToOriginalY = roundedModelY / actualScaleFactor;

      const finalRoundedX = Math.round(manualBackToOriginalX);
      const finalRoundedY = Math.round(manualBackToOriginalY);

      // Get results from the scaler for comparison
      const modelCoords = scaler.scaleToModelSpace(originalPoint);
      const roundTrip = scaler.scaleToOriginalSpace(modelCoords);

      console.log(
        `\nTarget: "${target.name}" at [${originalPoint[0]}, ${originalPoint[1]}]:`
      );
      console.log(
        `  Exact model coords: [${manualToModelX.toFixed(
          3
        )}, ${manualToModelY.toFixed(3)}]`
      );
      console.log(
        `  Rounded model coords: [${roundedModelX}, ${roundedModelY}]`
      );
      console.log(
        `  Scaler model coords: [${modelCoords[0]}, ${modelCoords[1]}]`
      );

      if (
        roundedModelX !== modelCoords[0] ||
        roundedModelY !== modelCoords[1]
      ) {
        console.log(
          `  ⚠️ Model coordinate calculation differs from manual calculation!`
        );
      }

      console.log(
        `  Exact reverse transform: [${manualBackToOriginalX.toFixed(
          3
        )}, ${manualBackToOriginalY.toFixed(3)}]`
      );
      console.log(
        `  Final rounded coords: [${finalRoundedX}, ${finalRoundedY}]`
      );
      console.log(`  Scaler round-trip: [${roundTrip[0]}, ${roundTrip[1]}]`);

      if (finalRoundedX !== roundTrip[0] || finalRoundedY !== roundTrip[1]) {
        console.log(
          `  ⚠️ Round-trip calculation differs from manual calculation!`
        );
      }

      // Calculate error and check if target would be hit
      const error = [
        roundTrip[0] - originalPoint[0],
        roundTrip[1] - originalPoint[1],
      ];
      const errorMagnitude = Math.sqrt(error[0] ** 2 + error[1] ** 2);

      console.log(`  Error vector: [${error[0]}, ${error[1]}]`);
      console.log(`  Error magnitude: ${errorMagnitude.toFixed(2)} pixels`);
      console.log(
        `  Target hit? ${
          errorMagnitude <= target.size / 2 ? "✅ YES" : "❌ NO"
        }`
      );

      // Subpixel analysis
      const subpixelLossX = Math.abs(manualToModelX - roundedModelX);
      const subpixelLossY = Math.abs(manualToModelY - roundedModelY);

      console.log(
        `  Subpixel rounding loss: [${subpixelLossX.toFixed(
          3
        )}, ${subpixelLossY.toFixed(3)}]`
      );

      if (subpixelLossX > 0.4 || subpixelLossY > 0.4) {
        console.log(`  ⚠️ High subpixel rounding loss detected!`);
      }
    }
  }

  // Suggest potential fixes
  console.log("\n\n=== Potential Issues and Fixes ===");
  console.log(
    "1. Scale factor calculation may not preserve small targets when using geometric mean"
  );
  console.log(
    "   → Consider using min(xScale, yScale) to ensure coordinates are never rounded beyond target"
  );
  console.log(
    "2. Double rounding during coordinate transforms may compound errors"
  );
  console.log("   → Store intermediate calculations with higher precision");
  console.log(
    "3. For small targets, the transformation bias may consistently miss in one direction"
  );
  console.log(
    "   → Add small bias correction for tiny targets or use ceiling/floor instead of round"
  );
}

// Run the tests
runResolutionScalerTests().catch(console.error);
