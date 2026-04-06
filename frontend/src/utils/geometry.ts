/**
 * Rotates a point around a center by a given angle in degrees.
 * @param x The x coordinate of the point.
 * @param y The y coordinate of the point.
 * @param cx The x coordinate of the rotation center.
 * @param cy The y coordinate of the rotation center.
 * @param angleDeg The rotation angle in degrees.
 * @returns The rotated {x, y} coordinates.
 */
export const rotatePoint = (
  x: number,
  y: number,
  cx: number,
  cy: number,
  angleDeg: number
): { x: number; y: number } => {
  if (angleDeg === 0) return { x, y };

  const rad = (angleDeg * Math.PI) / 180;
  const dx = x - cx;
  const dy = y - cy;

  return {
    x: dx * Math.cos(rad) - dy * Math.sin(rad) + cx,
    y: dx * Math.sin(rad) + dy * Math.cos(rad) + cy,
  };
};
