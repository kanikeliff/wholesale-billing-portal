import { useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";

import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

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
    <div style={{
      background: "#f4f6f9",
      padding: "12px",
      borderRadius: "8px"
    }}>
      <div style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: "12px",
        flexWrap: "wrap",
        marginBottom: "12px"
      }}>
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

      <div style={{
        height: "680px",
        overflow: "auto",
        background: "#e9edf2",
        border: "1px solid #e2e6ed",
        borderRadius: "8px",
        padding: "12px",
        display: "flex",
        justifyContent: "center",
        alignItems: "flex-start"
      }}>
        <Document
          file={fileUrl}
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
          />
        </Document>
      </div>
    </div>
  );
}
