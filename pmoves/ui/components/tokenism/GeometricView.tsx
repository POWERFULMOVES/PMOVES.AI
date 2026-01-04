/* ═══════════════════════════════════════════════════════════════════════════
   Tokenism Geometric View

   CHIT hyperbolic geometry visualization using Poincaré disk model.
   Displays wealth distribution as geometric data points.
   ═══════════════════════════════════════════════════════════════════════════ */

"use client";

import { useEffect, useRef, useState } from 'react';
import { SimulationResult, getTokenismClient, CGPPacket } from '@/lib/tokenismClient';

interface GeometricViewProps {
  result?: SimulationResult | null;
  week?: number;
}

interface PoincarePoint {
  x: number;
  y: number;
  wealth: number;
  color: string;
}

/**
 * Convert Euclidean coordinates to Poincaré disk representation.
 * Maps wealth distribution to hyperbolic space within unit disk.
 */
function toPoincareDisk(wealth: number, maxWealth: number, angle: number): PoincarePoint {
  // Normalize wealth to [0, 1] range
  const normalized = Math.min(wealth / maxWealth, 1);

  // Hyperbolic distance from center (richer = closer to edge)
  // Using inverse hyperbolic tangent for hyperbolic mapping
  const r = Math.tanh(normalized * 2);

  const x = r * Math.cos(angle);
  const y = r * Math.sin(angle);

  // Color based on wealth quintile
  const quintile = Math.floor(normalized * 5);
  const colors = ['#22c55e', '#84cc16', '#eab308', '#f97316', '#ef4444'];
  const color = colors[Math.min(quintile, 4)];

  return { x, y, wealth, color };
}

/**
 * Draw Poincaré disk model with hyperbolic geodesics.
 */
function drawPoincareDisk(
  ctx: CanvasRenderingContext2D,
  points: PoincarePoint[],
  edges: [number, number][],
  width: number,
  height: number,
  center: { x: number; y: number },
  radius: number,
) {
  // Clear canvas
  ctx.clearRect(0, 0, width, height);

  // Draw unit disk boundary
  ctx.beginPath();
  ctx.arc(center.x, center.y, radius, 0, Math.PI * 2);
  ctx.strokeStyle = '#a78bfa';
  ctx.lineWidth = 2;
  ctx.stroke();

  // Draw hyperbolic grid (geodesics)
  ctx.strokeStyle = '#a78bfa20';
  ctx.lineWidth = 1;

  // Radial geodesics
  for (let i = 0; i < 12; i++) {
    const angle = (i / 12) * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(center.x, center.y);
    ctx.lineTo(
      center.x + radius * Math.cos(angle),
      center.y + radius * Math.sin(angle),
    );
    ctx.stroke();
  }

  // Concentric circles (hyperbolic "circles" = Euclidean circles with different centers)
  for (let i = 1; i <= 4; i++) {
    const r = (i / 4) * radius * 0.9;
    ctx.beginPath();
    ctx.arc(center.x, center.y, r, 0, Math.PI * 2);
    ctx.stroke();
  }

  // Draw edges (network connections)
  ctx.strokeStyle = '#ffffff30';
  ctx.lineWidth = 0.5;
  edges.forEach(([i, j]) => {
    if (points[i] && points[j]) {
      ctx.beginPath();
      ctx.moveTo(
        center.x + points[i].x * radius,
        center.y + points[i].y * radius,
      );
      ctx.lineTo(
        center.x + points[j].x * radius,
        center.y + points[j].y * radius,
      );
      ctx.stroke();
    }
  });

  // Draw points
  points.forEach((point) => {
    const px = center.x + point.x * radius;
    const py = center.y + point.y * radius;

    // Glow effect
    const gradient = ctx.createRadialGradient(px, py, 0, px, py, 8);
    gradient.addColorStop(0, point.color + 'cc');
    gradient.addColorStop(1, point.color + '00');

    ctx.beginPath();
    ctx.arc(px, py, 8, 0, Math.PI * 2);
    ctx.fillStyle = gradient;
    ctx.fill();

    // Point
    ctx.beginPath();
    ctx.arc(px, py, 3, 0, Math.PI * 2);
    ctx.fillStyle = point.color;
    ctx.fill();
  });

  // Center marker
  ctx.beginPath();
  ctx.arc(center.x, center.y, 2, 0, Math.PI * 2);
  ctx.fillStyle = '#fbbf24';
  ctx.fill();
}

export function TokenismGeometricView({ result, week }: GeometricViewProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [cgp, setCgp] = useState<CGPPacket | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [points, setPoints] = useState<PoincarePoint[]>([]);
  const [hoveredPoint, setHoveredPoint] = useState<PoincarePoint | null>(null);

  const tokenism = getTokenismClient();

  // Load geometry when result changes
  useEffect(() => {
    if (!result) {
      setPoints([]);
      setCgp(null);
      return;
    }

    setLoading(true);
    setError(null);

    tokenism.getGeometry(result.simulationId, week)
      .then((data) => {
        setCgp(data);

        // Convert CGP points to Poincaré disk representation
        const maxWealth = Math.max(
          ...data.geometry.points.map((p) => p[0] || 1),
          result.finalAvgWealth * 2,
        );

        const newPoints = data.geometry.points.map((point, index) => {
          const wealth = point[0] || result.finalAvgWealth;
          const angle = point[1] !== undefined ? point[1] : (index / data.geometry.points.length) * Math.PI * 2;
          return toPoincareDisk(wealth, maxWealth, angle);
        });

        setPoints(newPoints);
      })
      .catch((err) => {
        const errorMessage = err instanceof Error ? err.message : 'Failed to load geometry';
        console.error('Failed to load geometry:', err);
        setError(errorMessage);
        setPoints([]);  // Clear points on error - don't show synthetic/fake data
      })
      .finally(() => {
        setLoading(false);
      });
  }, [result, week, tokenism]);

  // Draw on canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || points.length === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas size
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * window.devicePixelRatio;
    canvas.height = rect.height * window.devicePixelRatio;

    const center = {
      x: canvas.width / 2,
      y: canvas.height / 2,
    };
    const radius = Math.min(canvas.width, canvas.height) / 2 - 20;

    const edges = cgp?.geometry.edges || [];

    drawPoincareDisk(ctx, points, edges, canvas.width, canvas.height, center, radius);
  }, [points, cgp]);

  // Handle mouse move for hover effects
  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const mouseX = (e.clientX - rect.left) * window.devicePixelRatio;
    const mouseY = (e.clientY - rect.top) * window.devicePixelRatio;

    const center = {
      x: canvas.width / 2,
      y: canvas.height / 2,
    };
    const radius = Math.min(canvas.width, canvas.height) / 2 - 20;

    // Find hovered point
    let found: PoincarePoint | null = null;
    for (const point of points) {
      const px = center.x + point.x * radius;
      const py = center.y + point.y * radius;
      const dist = Math.sqrt((mouseX - px) ** 2 + (mouseY - py) ** 2);

      if (dist < 15) {
        found = point;
        break;
      }
    }

    setHoveredPoint(found);
  };

  return (
    <div className="space-y-4">
      {/* Canvas */}
      <div className="relative flex justify-center items-center bg-black/50 border border-violet-500/30 rounded-lg" style={{ minHeight: '400px' }}>
        <canvas
          ref={canvasRef}
          width={800}
          height={400}
          className="w-full h-full"
          onMouseMove={handleMouseMove}
          onMouseLeave={() => setHoveredPoint(null)}
        />

        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/50">
            <div className="flex items-center gap-3 text-violet-400">
              <span className="w-5 h-5 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
              <span className="font-pixel text-sm">Loading CHIT geometry...</span>
            </div>
          </div>
        )}

        {!loading && !result && (
          <div className="absolute inset-0 flex items-center justify-center">
            <p className="text-gray-500 font-pixel text-sm">Run a simulation to see geometric visualization</p>
          </div>
        )}
      </div>

      {/* Legend */}
      {points.length > 0 && (
        <div className="flex items-center justify-center gap-6 text-xs">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-green-500" />
            <span className="text-gray-400">Low Wealth</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-yellow-500" />
            <span className="text-gray-400">Medium Wealth</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-red-500" />
            <span className="text-gray-400">High Wealth</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-violet-400" />
            <span className="text-gray-400">Poincaré Disk</span>
          </div>
        </div>
      )}

      {/* Hover Info */}
      {hoveredPoint && (
        <div className="absolute bottom-4 right-4 p-3 bg-black/90 border border-gold-500/50 rounded">
          <div className="text-xs font-mono text-gray-400">Wealth</div>
          <div className="font-pixel text-gold-400 text-lg">${hoveredPoint.wealth.toFixed(2)}</div>
        </div>
      )}

      {/* CGP Metadata */}
      {cgp && (
        <div className="p-3 border border-gray-800 bg-black/30 text-xs font-mono">
          <div className="flex items-center gap-4 text-gray-500">
            <span>CGP v{cgp.cgpVersion}</span>
            <span>|</span>
            <span>{cgp.packetType}</span>
            <span>|</span>
            <span>{cgp.geometry.manifold} manifold</span>
            <span>|</span>
            <span>{cgp.geometry.points.length} points</span>
            <span>|</span>
            <span>{cgp.geometry.edges.length} edges</span>
          </div>
        </div>
      )}

      {/* Description */}
      <div className="p-4 border border-violet-500/20 bg-violet-500/5">
        <h4 className="text-sm font-pixel text-violet-400 mb-2">Poincaré Disk Model</h4>
        <p className="text-xs text-gray-400 leading-relaxed">
          This visualization uses hyperbolic geometry (Poincaré disk model) to represent wealth distribution.
          Points closer to the disk boundary represent higher wealth levels. The hyperbolic distance from center
          follows the formula: d = artanh(r), where r is the Euclidean radius. This model preserves
          angular relationships while compressing infinite hyperbolic space into a finite unit disk.
        </p>
      </div>
    </div>
  );
}

export default TokenismGeometricView;
