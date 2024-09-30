import {Feature, Polygon, LineString, Point} from "geojson";

// Implementation of GJK algorithm for determining whether two polygons are within a distance of each other
// Adapted from https://dyn4j.org/2010/04/gjk-gilbert-johnson-keerthi/ and https://github.com/kroitor/gjk.c

//-----------------------------------------------------------------------------
// 2d Vector arithmetic operations
function subtract(a: number[], b: number[]): number[] {
    return [a[0] - b[0], a[1] - b[1]];
}

function negate(v: number[]): number[] {
    return [-v[0], -v[1]];
}

function dotProduct(a: number[], b: number[]): number {
    return a[0] * b[0] + a[1] * b[1];
}

function squaredMagnitude(v: number[]): number {
    return dotProduct(v, v);
}

function multiply(v: number[], s: number): number[] {
    return [v[0] * s, v[1] * s];
}

function add(a: number[], b: number[]): number[] {
    return [a[0] + b[0], a[1] + b[1]];
}

function equals(a: number[], b: number[]): boolean {
    return (a[0] === b[0] && a[1] === b[1]);
}

//-----------------------------------------------------------------------------
// Triple product expansion is used to calculate perpendicular normal vectors
// which prefer pointing towards the Origin in Minkowski space
function tripleProduct(a: number[], b: number[], c: number[]): number[] {
    const ac = dotProduct(a, c);
    const bc = dotProduct(b, c);

    // perform b * a.dot(c) - a * b.dot(c)
    return subtract(multiply(b, ac), multiply(a, bc));
}

//-----------------------------------------------------------------------------
// This is to compute average center (roughly). It might be different from
// Center of Gravity, especially for bodies with nonuniform density,
// but this is ok as initial direction of simplex search in GJK.
function averagePoint(vertices: number[][]): number[] {
    const avg = vertices.reduce((acc, v) => ([acc[0] + v[0], acc[1] + v[1]]), [0, 0]);
    return [avg[0] / vertices.length, avg[1] / vertices.length];
}

//-----------------------------------------------------------------------------
// Get furthest vertex along a certain direction
function indexOfFurthestPoint(vertices: number[][], d: number[]): number {
    let maxProduct = dotProduct(d, vertices[0]);
    let index = 0;
    for (let i = 1; i < vertices.length; i++) {
        const product = dotProduct(d, vertices[i]);

        if (product > maxProduct) {
            maxProduct = product;
            index = i;
        }
    }
    return index;
}

//-----------------------------------------------------------------------------
// Minkowski sum support function for GJK
function support(vertices1: number[][], vertices2: number[][], d: number[]): number[] {
    // get the furthest point of first body along an arbitrary direction
    const i = indexOfFurthestPoint(vertices1, d);

    // get the furthest point of second body along the opposite direction
    const j = indexOfFurthestPoint(vertices2, negate(d));

    // subtract (Minkowski sum) the two points
    return subtract(vertices1[i], vertices2[j]);
}

//-----------------------------------------------------------------------------
// Returns squared magnitude of point along the line connecting a and b which is closest to the origin
function squaredMinimumDistance(a: number[], b: number[]): number {
    if (equals(a, b)) {
        return squaredMagnitude(a);
    }

    // calculate distance along ab which is the closest point to the origin
    const ab = subtract(b, a);
    let distance = dotProduct(negate(a), ab) / squaredMagnitude(ab);

    // if the point is off the line segment, snap it to the end of the segment
    if (distance > 1) {
        distance = 1;
    } else if (distance < 0) {
        distance = 0;
    }

    const closestPoint = add(multiply(ab, distance), a);

    return squaredMagnitude(closestPoint)
}

//-----------------------------------------------------------------------------
// Returns true if the origin is in the triangle, false otherwise.
// Barycentric coordinate method from Christer Ericson's Real-Time Collision Detection
function enclosesOrigin(a: number[], b: number[], c: number[]): boolean {
    const v0 = subtract(b, a);
    const v1 = subtract(c, a);
    const v2 = negate(a);
    const d00 = dotProduct(v0, v0);
    const d01 = dotProduct(v0, v1);
    const d11 = dotProduct(v1, v1);
    const d20 = dotProduct(v2, v0);
    const d21 = dotProduct(v2, v1);
    const denom = d00 * d11 - d01 * d01;

    // points are collinear. Check if origin is a convex combination of a, b, c
    // small error for float imprecision
    if (denom <= Number.EPSILON * 1000) {
        let points = [a, b, c];
        // sort by x then y (y necessary in case its vertical)
        points.sort((point1, point2) => {
            if (point1[0] !== point2[0]) {
                return point1[0] - point2[0];
            } else {
                return point1[1] - point2[1];
            }
        });

        return (
            Math.abs(points[0][0] * points[2][1] - points[0][1] * points[2][0])
            <= Number.EPSILON * 1000 && points[0][1] >= 0 && points[2][1] <= 0
        );
    }

    const inverseDenom = 1 / denom;
    const v = (d11 * d20 - d01 * d21) * inverseDenom;
    const w = (d00 * d21 - d01 * d20) * inverseDenom;
    const u = 1.0 - v - w;

    return (v >= 0 && w >= 0 && u >= 0);
}

//-----------------------------------------------------------------------------
// Returns True if the shapes are within distance of each other, False otherwise. Based on the GJK distance algorithm.
function polygonsWithinDistance(
    vertices1: number[][],
    vertices2: number[][],
    distance: number,
    max_iterations: number = 20
): boolean {
    // at some near zero distance, the direction found by tripleProduct becomes inaccurate due to float imprecision and
    // closely overlapping shapes will sometimes return False.
    // you could potentially allow this and live with some incorrect returns, but it should always be non-negative.
    if (distance < Number.EPSILON * 1000) {
        throw new Error("polygonsWithinDistance: Choose a distance greater than 0.");
    }

    let a: number[], b: number[], c: number[], d: number[], ab: number[], ao: number[];
    const threshold: number = distance * distance; // Comparing squared distances

    // initial direction from the center of 1st body to the center of 2nd body
    d = subtract(averagePoint(vertices1), averagePoint(vertices2));

    // if initial direction is zero the shapes overlap since they are convex.
    // also prevents issues with finding the support
    if (Math.abs(d[0]) < Number.EPSILON * 1000 && Math.abs(d[1]) < Number.EPSILON * 1000) {
        return true;
    }

    // set the first two supports as initial points of the simplex
    a = support(vertices1, vertices2, d);
    b = support(vertices1, vertices2, negate(a));

    // the next search direction is perpendicular to ab towards the origin
    ab = subtract(b, a);
    ao = negate(a);
    d = tripleProduct(ab, ao, ab);

    let minDistance = squaredMinimumDistance(a, b);

    for (let i = 0; i < max_iterations; i++) {
        c = support(vertices1, vertices2, d);

        if (minDistance < threshold || enclosesOrigin(a, b, c)) {
            return true;
        }

        // we already know that c is closer to the origin than both a and b,
        // so keep c and choose which of a and b to keep
        const acClosest = squaredMinimumDistance(a, c);
        const bcClosest = squaredMinimumDistance(b, c);
        const oldDistance = minDistance;

        if (acClosest < bcClosest) {
            b = c;
            minDistance = acClosest;
        } else {
            a = c;
            minDistance = bcClosest;
        }

        // if not making progress, return
        if (oldDistance - minDistance <= 0) {
            return minDistance < threshold;
        }

        ab = subtract(b, a);
        ao = negate(a);
        d = tripleProduct(ab, ao, ab);
    }

    // ended due to max_iterations
    return minDistance < threshold;
}

//-----------------------------------------------------------------------------
// Helper function which runs polygonsWithinDistance on a GeoJSON object
export function convexHullsWithinDistance(
    shape1: Feature<Polygon> | Feature<LineString> | Feature<Point>,
    shape2: Feature<Polygon> | Feature<LineString> | Feature<Point>,
    distanceMeters: number
): boolean {
    let points1: number[][], points2: number[][];

    // extract coordinates based on geometry type
    if (shape1.geometry.type === 'Polygon') {
        points1 = shape1.geometry.coordinates[0];
    } else if (shape1.geometry.type === 'LineString') {
        points1 = shape1.geometry.coordinates;
    } else {
        points1 = [shape1.geometry.coordinates];
    }

    if (shape2.geometry.type === 'Polygon') {
        points2 = shape2.geometry.coordinates[0];
    } else if (shape2.geometry.type === 'LineString') {
        points2 = shape2.geometry.coordinates;
    } else {
        points2 = [shape2.geometry.coordinates];
    }

    const center = averagePoint(points1.concat(points2));
    const points1XY = localTangentPlaneProjection(points1, center);
    const points2XY = localTangentPlaneProjection(points2, center);

    return polygonsWithinDistance(points1XY, points2XY, distanceMeters);
}

//-----------------------------------------------------------------------------
// Local tangent plane projection
// Very inaccurate over large distances, but we only care about exact differences between ~10m
function localTangentPlaneProjection(points: number[][], center: number[]): number[][] {
    const R = 6371e3;  // Earth's radius
    const centerLatRad = center[1] * Math.PI / 180;
    const centerLonRad = center[0] * Math.PI / 180;

    return points.map(point => {
        const lat = point[1];
        const lon = point[0];

        // convert latitude and longitude to radians
        const latRad = lat * Math.PI / 180;
        const lonRad = lon * Math.PI / 180;

        const x = R * Math.cos(latRad) * Math.sin(lonRad - centerLonRad);
        const y = (
            R * (Math.cos(centerLatRad) * Math.sin(latRad) -
                Math.sin(centerLatRad) * Math.cos(latRad) * Math.cos(lonRad - centerLonRad))
        );

        return [x, y];
    });
}

//-----------------------------------------------------------------------------
// TESTING FUNCTIONS
function jostleVertices(vertices: number[][]): number[][] {
    return vertices.map(v => ([
        v[0] + (Math.random() * Number.EPSILON * 100.0) * (Math.random() < 0.5 ? 1.0 : -1.0),
        v[1] + (Math.random() * Number.EPSILON * 100.0) * (Math.random() < 0.5 ? 1.0 : -1.0)
    ]));
}

//Takes 2 shapes, a low distance within which they should not intersect and a high distance within which they should
function testPolygons(a: number[][], b: number[][], low: number, high: number, jostle: boolean = true) {
    // if they intersect, no need to check a low distance because it should always return true
    if (low > 0 && polygonsWithinDistance(a, b, low)) {
        throw Error("Failed low");
    } else if (!polygonsWithinDistance(a, b, high)) {
        throw Error("Failed high");
    }

    if (jostle) {
        let aJostled: number[][], bJostled: number[][];

        for (let i = 0; i < 100; i++) {
            aJostled = jostleVertices(a);
            bJostled = jostleVertices(b);

            if (low > 0 && polygonsWithinDistance(aJostled, bJostled, low)) {
                console.log(aJostled, bJostled);
                throw Error(`Failed low jostle ${i}`);
            }

            if (!polygonsWithinDistance(aJostled, bJostled, high)) {
                console.log(aJostled, bJostled);
                throw Error(`Failed high jostled ${i}`);
            }
        }
    }
}

// Various test cases for polygonsWithinDistance
function testPolygonsWithinDistance() {
    let a: number[][], b: number[][];

    const eps = Number.EPSILON * 1000;

    // distance about 1.7179113807
    a = [
        [4.0, 11.0],
        [9.0, 9.0],
        [4.0, 5.0],
    ];
    b = [
        [8.0, 6.0],
        [10.0, 2.0],
        [13.0, 1.0],
        [15.0, 6.0],
    ];
    testPolygons(a, b, 1.7179113807, 1.7179113808);
    console.log("Passed distance 1.7179113807");

    // overlapping slightly
    a = [
        [4, 11],
        [4, 5],
        [9, 9],
    ];
    b = [
        [5, 7],
        [7, 3],
        [10, 2],
        [12, 7],
    ];
    testPolygons(a, b, 0.0, eps);
    console.log("Passed overlapping");

    // overlapping perfectly
    a = [
        [4, 11],
        [4, 5],
        [9, 9],
    ];
    b = [
        [4, 11],
        [4, 5],
        [9, 9],
    ];
    testPolygons(a, b, 0.0, eps);
    console.log("Passed overlapping perfectly");

    // parallel lines
    a = [
        [1, 1],
        [-1, 1],
        [-2, 1],
    ];
    b = [
        [1, -1],
        [-1, -1],
        [-2, -1],
    ];
    testPolygons(a, b, 2 - eps, 2 + eps);
    console.log("Passed parallel");

    // points
    a = [
        [1, 1],
    ];
    b = [
        [1, -1],
    ];
    testPolygons(a, b, 2 - eps, 2 + eps);
    console.log("Passed points");

    // overlapping points
    a = [
        [1, 1],
    ];
    b = [
        [1, 1],
    ];
    testPolygons(a, b, 0.0, eps);
    console.log("Passed equal points");

    // polygon within polygon
    a = [
        [1, 1],
        [-1, 1],
        [1, -1],
        [-1, -1],
    ];
    b = [
        [2, 2],
        [-2, 2],
        [2, -2],
        [-2, -2],
    ];
    testPolygons(a, b, 0.0, eps);
    console.log("Passed polygon within polygon");

    // shared edge
    a = [
        [1, 1],
        [3, 1],
        [2, 3],
    ];
    b = [
        [3, 1],
        [5, 1],
        [4, 3],
    ];
    testPolygons(a, b, 0.0, eps);
    console.log("Passed shared edge");

    // touching at a single point
    a = [
        [1, 1],
        [3, 1],
        [2, 3],
    ];
    b = [
        [2, 3],
        [4, 3],
        [3, 5],
    ];
    testPolygons(a, b, 0.0, eps);
    console.log("Passed touching at a single point");

    // large coordinates
    a = [
        [1e6, 1e6],
        [1e6 + 1, 1e6],
        [1e6, 1e6 + 1],
    ];
    b = [
        [1e6 + 2, 1e6],
        [1e6 + 2, 1e6 + 2],
        [1e6, 1e6 + 2],
    ];
    testPolygons(a, b, 1 / Math.sqrt(2) - eps, 1 / Math.sqrt(2) + eps);
    console.log("Passed large coordinates");

    // small/negative coordinates
    a = [
        [-10, -10],
        [-10 + 1, -10],
        [-10, -10 + 1],
    ];
    b = [
        [-10 + 2, -10],
        [-10 + 2, -10 + 2],
        [-10, -10 + 2],
    ];
    testPolygons(a, b, 1 / Math.sqrt(2) - eps, 1 / Math.sqrt(2) + eps);
    console.log("Passed small/negative coordinates");

    // zero-length edge
    a = [
        [1, 1],
        [1, 1],
    ];
    b = [
        [2, 2],
        [3, 3],
    ];
    testPolygons(a, b, Math.sqrt(2) - eps, Math.sqrt(2) + eps);
    console.log("Passed zero-length edge");

    // random failed test case from Serpent
    a = [
        [1556.6377561454135, -44.72004540878971],
        [1558.4082350260776, -45.46826017054581],
        [1546.9409013144616, 253.40577218944205],
        [1556.6377561454135, -44.72004540878971]
    ];
    b = [
        [-898.5031978032816, -35.29624052342881],
        [-888.3351677588042, -47.144935804310116],
        [-878.9339023989477, -23.214864710094123],
        [-875.6149420151786, 6.724985688568552],
        [-881.4986391783281, 34.5953895001195],
        [-897.0288108438825, -24.1872062188703],
        [-898.5031978032816, -35.29624052342881]
    ];

    testPolygons(a, b, 2429, 2430);
    console.log("Passed serpent test case");
}
