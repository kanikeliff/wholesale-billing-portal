import { useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";

import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import "./BolPdfViewer.css";

pdfjs.GlobalWorkerOptions.workerSrc = `${import.meta.env.BASE_URL}pdfjs-assets/pdf.worker.min.mjs`;

// Keep options stable so React-PDF does not reload on every render.
const pdfOptions = {
  wasmUrl: `${import.meta.env.BASE_URL}pdfjs-assets/`,
};

type BolPdfViewerProps = {
  fileUrl: string;
};

export default function BolPdfViewer({
  fileUrl,
}: BolPdfViewerProps) {
  const [numPages, setNumPages] = useState(0);
  const [pageNumber, setPageNumber] = useState(1);
  const [width, setWidth] = useState(520);

  return (
    <div className="bol-pdf-viewer">
      <div className="bol-pdf-toolbar">
        <div>
          <button
            type="button"
            disabled={pageNumber <= 1}
            onClick={() =>
              setPageNumber((p) => Math.max(1, p - 1))
            }
          >
            Previous
          </button>

          <span style={{ margin: "0 12px" }}>
            Page {pageNumber} of {numPages || "—"}
          </span>

          <button
            type="button"
            disabled={!numPages || pageNumber >= numPages}
            onClick={() =>
              setPageNumber((p) =>
                Math.min(numPages, p + 1)
              )
            }
          >
            Next
          </button>
        </div>

        <div>
          <button
            type="button"
            onClick={() =>
              setWidth((w) => Math.max(300, w - 80))
            }
          >
            −
          </button>

          <span style={{ margin: "0 10px" }}>
            Zoom
          </span>

          <button
            type="button"
            onClick={() =>
              setWidth((w) => Math.min(1000, w + 80))
            }
          >
            +
          </button>
        </div>
      </div>

      <div className="bol-pdf-scroll">
        <div className="bol-pdf-stage">
          <Document
            file={fileUrl}
            options={pdfOptions}
            onLoadSuccess={({ numPages }) => {
              setNumPages(numPages);
              setPageNumber(1);
            }}
            loading={<p>Loading PDF...</p>}
            error={
              <p style={{ color: "#b91c1c" }}>
                Unable to display PDF.
              </p>
            }
          >
            <Page
              pageNumber={pageNumber}
              width={width}
              renderTextLayer={false}
              renderAnnotationLayer={false}
            />
          </Document>
        </div>
      </div>
    </div>
  );
}
