#!/usr/bin/env node
/**
 * Generate PDF from HTML using Puppeteer with custom footer template.
 * Strategy: Generate full PDF (all pages with footer + working internal links),
 * then replace cover page with a clean version (no footer, zero margins).
 * Finally adds clickable LinkedIn link annotations via pdf-lib.
 *
 * Usage: node generate-pdf.cjs <html-file> [output-pdf]
 *
 * Requires: puppeteer, pdf-lib
 */
const puppeteer = require('puppeteer');
const { PDFDocument, PDFName, PDFString } = require('pdf-lib');
const fs = require('fs');
const path = require('path');

const htmlPath = process.argv[2];
const outputPath = process.argv[3] || '/tmp/presupuesto-test.pdf';

if (!htmlPath) {
    console.error('Usage: node generate-pdf.cjs <html-file> [output-pdf]');
    process.exit(1);
}

const LINKEDIN_URL = process.env.LINKEDIN_URL || 'https://www.linkedin.com/in/your-profile/';

const LINKEDIN_PNG = 'iVBORw0KGgoAAAANSUhEUgAAADAAAAAwCAYAAABXAvmHAAAAAXNSR0IArs4c6QAAAZVJREFUaIHtmU2SgjAQhV9Tcy/jTg7BDeQM4hngBjkE7CaerGcTR4rKnzAmTQ3fypIs+tk/eTYEAL0eFYFuABT2gWHwo23qjno9djb43cHgc0WgU+lA1kKgW7WjsnGhqtIRbGX3Ar4Sz5nZZ1ElFxXA4HPb1HMBkDS5giXE4PsyeABom7pbZKUYIQHGBuqEwffPhPQeXgEMfuQNZR1eAQkXnIhmDpWQiABjBJt40NO363tJU4gGPXHkjLH9YGD9h6TspFxkikAKgIhffMm/sRKfwCxH9Zq+Cgq4NhfyPbMNPu8Fc20uZ9fZedO7rMmMrtejsmWbJCZnBozPmsyxz02vx6SMZBPgy46Ptqm7QU+n2MTL0sQhTxUixW+JnkLPcgqdKSKg16OyzbqZrGN0aUEGPT3/cwRtu71InWTLgM8/Eei2JRvZBETsuXwBoSC3LNdETyG8JpGXLAL+auK4EJ+BGIeA0hwCSnMIKM0hoDSHgNKkrBZFs/sMHAJKU0l5WbcSU0l5WbcGBj8Ir41BdI0niN896w837Ys8QvzqQQAAAABJRU5ErkJggg==';

const footerTemplate = `
<div style="width: 100%; text-align: center; padding: 0;">
    <span style="font-size: 8px; color: #94A3B8; font-family: -apple-system, BlinkMacSystemFont, sans-serif;">Victor Manuel Ramirez Marcos</span>
    <span style="font-size: 8px; color: #94A3B8; margin: 0 3px;">&middot;</span>
    <img src="data:image/png;base64,${LINKEDIN_PNG}" style="width: 10px; height: 10px; vertical-align: middle; opacity: 0.6;" />
</div>`;

async function buildPDF(fullPath, coverPath, outPath) {
    // Load the full PDF (has working internal links via Names/Dests dictionary)
    var fullDoc = await PDFDocument.load(fs.readFileSync(fullPath));
    var coverDoc = await PDFDocument.load(fs.readFileSync(coverPath));

    // Copy clean cover page (no footer) into the full document
    var [newCover] = await fullDoc.copyPages(coverDoc, [0]);

    // Replace page 0 (cover with unwanted footer) with clean cover
    fullDoc.removePage(0);
    fullDoc.insertPage(0, newCover);

    // Add clickable LinkedIn link annotations on content pages (index 1+)
    var pages = fullDoc.getPages();
    var linkRect = [42.52, 0, 552.76, 62.36];

    for (var i = 1; i < pages.length; i++) {
        var page = pages[i];

        var linkAnnotation = fullDoc.context.register(
            fullDoc.context.obj({
                Type: 'Annot',
                Subtype: 'Link',
                Rect: linkRect,
                Border: [0, 0, 0],
                A: {
                    Type: 'Action',
                    S: 'URI',
                    URI: PDFString.of(LINKEDIN_URL),
                },
            })
        );

        var existingAnnots = page.node.lookup(PDFName.of('Annots'));
        if (existingAnnots) {
            existingAnnots.push(linkAnnotation);
        } else {
            page.node.set(PDFName.of('Annots'), fullDoc.context.obj([linkAnnotation]));
        }
    }

    fs.writeFileSync(outPath, await fullDoc.save());

    // Clean up temp files
    fs.unlinkSync(fullPath);
    fs.unlinkSync(coverPath);
}

async function generatePDF() {
    var browser = await puppeteer.launch({
        headless: 'new',
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    var page = await browser.newPage();

    var absolutePath = path.resolve(htmlPath);
    await page.goto('file://' + absolutePath, {
        waitUntil: 'networkidle0',
        timeout: 30000
    });

    // Wait for fonts and JS to execute
    await new Promise(function(r) { setTimeout(r, 2000); });

    var fullPath = outputPath + '.full.tmp';
    var coverPath = outputPath + '.cover.tmp';

    // Pass 1: Full PDF with footer on ALL pages (preserves internal links)
    await page.pdf({
        path: fullPath,
        format: 'A4',
        printBackground: true,
        displayHeaderFooter: true,
        headerTemplate: '<span></span>',
        footerTemplate: footerTemplate,
        margin: {
            top: '18mm',
            right: '15mm',
            bottom: '22mm',
            left: '15mm'
        }
    });

    // Pass 2: Cover page only without footer (clean cover)
    await page.pdf({
        path: coverPath,
        format: 'A4',
        printBackground: true,
        displayHeaderFooter: false,
        pageRanges: '1',
        margin: { top: '0', right: '0', bottom: '0', left: '0' }
    });

    await browser.close();

    // Replace cover in full PDF and add clickable link annotations
    await buildPDF(fullPath, coverPath, outputPath);

    console.log('PDF generated: ' + outputPath);
}

generatePDF().catch(function(err) {
    console.error('Error:', err.message);
    process.exit(1);
});
