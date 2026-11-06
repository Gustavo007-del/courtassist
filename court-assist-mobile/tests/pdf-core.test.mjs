import test from 'node:test';
import assert from 'node:assert/strict';
import { PDFDocument } from 'pdf-lib';
import { extractPdfBytes, mergePdfBytes, reorderPdfBytes, rotatePdfBytes } from '../src/features/scanner/pdf-core.ts';

async function sample(sizes) { const pdf = await PDFDocument.create(); sizes.forEach(([width, height]) => pdf.addPage([width, height])); return pdf.save(); }
test('merge, extract, rotate, and reorder preserve requested pages', async () => {
  const first = await sample([[595, 842], [842, 595]]);
  const second = await sample([[400, 600]]);
  const merged = await mergePdfBytes([first, second]);
  const mergedDoc = await PDFDocument.load(merged);
  assert.equal(mergedDoc.getPageCount(), 3);
  const extracted = await PDFDocument.load(await extractPdfBytes(merged, [2, 0]));
  assert.deepEqual(extracted.getPages().map((page) => Math.round(page.getWidth())), [400, 595]);
  const rotated = await PDFDocument.load(await rotatePdfBytes(merged, [1], 90));
  assert.equal(rotated.getPage(1).getRotation().angle, 90);
  const reordered = await PDFDocument.load(await reorderPdfBytes(merged, [1, 0]));
  assert.deepEqual(reordered.getPages().map((page) => Math.round(page.getWidth())), [842, 595]);
  await assert.rejects(() => extractPdfBytes(merged, [9]));
  await assert.rejects(() => reorderPdfBytes(merged, [0, 0]));
});
