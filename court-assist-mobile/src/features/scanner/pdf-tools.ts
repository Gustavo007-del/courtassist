import { File } from 'expo-file-system';
import * as ImageManipulator from 'expo-image-manipulator';
import { PDFDocument, rgb } from 'pdf-lib';
import { extractPdfBytes, reorderPdfBytes, rotatePdfBytes } from './pdf-core';
import type { Compression, ScanPage } from './types';

export const A4 = { portrait: [595.28, 841.89] as const, landscape: [841.89, 595.28] as const };
const compression = { high: { quality: 0.96, max: 2800 }, balanced: { quality: 0.82, max: 2200 }, small: { quality: 0.64, max: 1600 } } as const;
export async function createPdfFromPages(pages: ScanPage[], quality: Compression, onProgress?: (done: number, total: number) => void): Promise<Uint8Array> {
  if (!pages.length) throw new Error('No pages selected');
  const pdf = await PDFDocument.create();
  const profile = compression[quality];
  for (let index = 0; index < pages.length; index++) {
    const item = pages[index];
    const scale = Math.min(1, profile.max / Math.max(item.width, item.height));
    const processed = await ImageManipulator.manipulateAsync(item.uri, scale < 1 ? [{ resize: { width: Math.round(item.width * scale) } }] : [], { format: ImageManipulator.SaveFormat.JPEG, compress: profile.quality });
    const image = await pdf.embedJpg(await new File(processed.uri).bytes());
    const landscape = image.width > image.height;
    const [width, height] = landscape ? A4.landscape : A4.portrait;
    const page = pdf.addPage([width, height]);
    const ratio = Math.min((width - 36) / image.width, (height - 36) / image.height);
    const drawWidth = image.width * ratio, drawHeight = image.height * ratio;
    page.drawImage(image, { x: (width - drawWidth) / 2, y: (height - drawHeight) / 2, width: drawWidth, height: drawHeight });
    const temporary = new File(processed.uri); if (temporary.exists && processed.uri !== item.uri) temporary.delete();
    onProgress?.(index + 1, pages.length);
  }
  return pdf.save({ useObjectStreams: true });
}
export async function pageCount(uri: string): Promise<number> { const pdf = await PDFDocument.load(await new File(uri).bytes()); return pdf.getPageCount(); }
export async function mergePdfs(uris: string[], onProgress?: (done: number, total: number) => void): Promise<Uint8Array> { if (uris.length < 2) throw new Error('Choose at least two PDFs'); const output = await PDFDocument.create(); for (let i = 0; i < uris.length; i++) { const source = await PDFDocument.load(await new File(uris[i]).bytes()); const copied = await output.copyPages(source, source.getPageIndices()); copied.forEach((page) => output.addPage(page)); onProgress?.(i + 1, uris.length); } return output.save({ useObjectStreams: true }); }
export async function extractPages(uri: string, indices: number[]): Promise<Uint8Array> { return extractPdfBytes(await new File(uri).bytes(), indices); }
export async function rotatePages(uri: string, indices: number[], angle: 90 | 180 | 270): Promise<Uint8Array> { return rotatePdfBytes(await new File(uri).bytes(), indices, angle); }
export async function reorderPdf(uri: string, indices: number[]): Promise<Uint8Array> { return reorderPdfBytes(await new File(uri).bytes(), indices); }
export type Annotation = { page: number; kind: 'highlight' | 'underline' | 'strike' | 'rectangle' | 'line' | 'text' | 'signature' | 'freehand'; x: number; y: number; width: number; height: number; color: [number, number, number]; text?: string; imageUri?: string; points?: { x: number; y: number }[] };
export async function annotatePdf(uri: string, annotations: Annotation[]): Promise<Uint8Array> {
  const pdf = await PDFDocument.load(await new File(uri).bytes());
  for (const note of annotations) {
    const page = pdf.getPage(note.page); const color = rgb(...note.color); const x = note.x * page.getWidth(), y = (1 - note.y - note.height) * page.getHeight(), width = note.width * page.getWidth(), height = note.height * page.getHeight();
    if (note.kind === 'highlight') page.drawRectangle({ x, y, width, height, color, opacity: 0.3 });
    else if (note.kind === 'rectangle') page.drawRectangle({ x, y, width, height, borderColor: color, borderWidth: 2, opacity: 0 });
    else if (note.kind === 'underline' || note.kind === 'strike' || note.kind === 'line') page.drawLine({ start: { x, y: y + (note.kind === 'strike' ? height / 2 : 0) }, end: { x: x + width, y: y + (note.kind === 'strike' ? height / 2 : 0) }, color, thickness: 2 });
    else if (note.kind === 'freehand' && note.points) for (let i = 1; i < note.points.length; i++) page.drawLine({ start: { x: note.points[i - 1].x * page.getWidth(), y: (1 - note.points[i - 1].y) * page.getHeight() }, end: { x: note.points[i].x * page.getWidth(), y: (1 - note.points[i].y) * page.getHeight() }, color, thickness: 2 });
    else if (note.kind === 'text' && note.text) page.drawText(note.text, { x, y, size: Math.max(8, Math.min(24, height)), color });
    else if (note.kind === 'signature' && note.imageUri) { const image = await pdf.embedPng(await new File(note.imageUri).bytes()); page.drawImage(image, { x, y, width, height }); }
  }
  return pdf.save({ useObjectStreams: true });
}
