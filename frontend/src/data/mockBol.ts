import type { BOLRecord } from "../types/bol";

export const mockBols: BOLRecord[] = [
  {
    recordId: "rec-001",
    bolNumber: "566836",
    contractLifting: "7305581202",
    origin: "ETP Fullerton, PA terminal",
    supplier: "Marathon",
    carrier: "Penn Tank Lines",
    transactionDate: "2026-09-17",
    destination: "Pennsylvania",
    lineItems: [
      {
        lineItemId: 1,
        product: "B2 Diesel Clear",
        e3StockId: "BD2",
        netGallons: 7443,
        grossGallons: 7500,
      },
    ],
    status: "NEEDS_REVIEW",
  },

  {
    recordId: "rec-002",
    bolNumber: "2569495",
    contractLifting: "8002339101",
    origin: "Shell Providence, RI terminal",
    supplier: "Sunoco",
    carrier: "Dennis K. Burke Inc.",
    transactionDate: "2026-09-15",
    destination: "Massachusetts",
    lineItems: [
      {
        lineItemId: 1,
        product: "NRLM",
        e3StockId: "ND",
        netGallons: 5971,
        grossGallons: 6000,
      },
    ],
    status: "OCR_COMPLETE",
  },

  {
    recordId: "rec-003",
    bolNumber: "813492",
    contractLifting: "574402",
    origin: "New Haven, CT",
    supplier: "Valero",
    carrier: "JP Noonan",
    transactionDate: "2026-09-18",
    destination: "Connecticut",
    lineItems: [
      {
        lineItemId: 1,
        product: "ULSD",
        e3StockId: "UD",
        netGallons: 6939,
        grossGallons: 7000,
      },
    ],
    status: "OCR_COMPLETE",
  },

  {
    recordId: "rec-004",
    bolNumber: "867187",
    contractLifting: "I 43117-3",
    origin: "Vestal, NY",
    supplier: "Buckeye",
    carrier: "Munroe Tank Lines",
    transactionDate: "2026-09-18",
    destination: "New York",
    lineItems: [
      {
        lineItemId: 1,
        product: "87 gas",
        e3StockId: "UX",
        netGallons: 6965,
        grossGallons: 7000,
      },
      {
        lineItemId: 2,
        product: "93 gas",
        e3StockId: "SX",
        netGallons: 2392,
        grossGallons: 2400,
      },
    ],
    status: "NEEDS_REVIEW",
  },

  {
    recordId: "rec-005",
    bolNumber: "239680",
    contractLifting: "224009",
    origin: "Glenmont, NY",
    supplier: "Citgo (FPA)",
    carrier: "Mirabito",
    transactionDate: "2026-09-17",
    destination: "New York",
    lineItems: [
      {
        lineItemId: 1,
        product: "ULSD",
        e3StockId: "UD",
        netGallons: 2984,
        grossGallons: 3000,
      },
    ],
    status: "OCR_COMPLETE",
  },

  {
    recordId: "rec-006",
    bolNumber: "239681",
    contractLifting: "327897",
    origin: "New York",
    supplier: "Citgo (BP)",
    carrier: "Mirabito",
    transactionDate: "2026-09-17",
    destination: "New York",
    lineItems: [
      {
        lineItemId: 1,
        product: "87 gas",
        e3StockId: "UX",
        netGallons: 5555,
        grossGallons: 5596,
      },
    ],
    status: "OCR_COMPLETE",
  },

  {
    recordId: "rec-007",
    bolNumber: "1996150",
    contractLifting: "40902",
    origin: "Pennsylvania",
    supplier: "PBF",
    carrier: "Mirabito",
    transactionDate: "2026-09-17",
    destination: "Pennsylvania",
    lineItems: [
      {
        lineItemId: 1,
        product: "87 gas",
        e3StockId: "UX",
        netGallons: 6456,
        grossGallons: 6500,
      },
      {
        lineItemId: 2,
        product: "93 gas",
        e3StockId: "SX",
        netGallons: 1495,
        grossGallons: 1500,
      },
    ],
    status: "NEEDS_REVIEW",
  },

  {
    recordId: "rec-008",
    bolNumber: "868375",
    contractLifting: "153",
    origin: "Brewerton, NY",
    supplier: "Mieco",
    carrier: "Mirabito",
    transactionDate: "2026-09-17",
    destination: "New York",
    lineItems: [
      {
        lineItemId: 1,
        product: "ULSD",
        e3StockId: "UD",
        netGallons: 7972,
        grossGallons: 8000,
      },
    ],
    status: "OCR_COMPLETE",
  },

  {
    recordId: "rec-009",
    bolNumber: "831062",
    contractLifting: "2345",
    origin: "Syracuse, NY",
    supplier: "Monroe",
    carrier: "Mirabito",
    transactionDate: "2026-09-17",
    destination: "New York",
    lineItems: [
      {
        lineItemId: 1,
        product: "87 gas",
        e3StockId: "UX",
        netGallons: 7473,
        grossGallons: 7500,
      },
      {
        lineItemId: 2,
        product: "93 gas",
        e3StockId: "SX",
        netGallons: 990,
        grossGallons: 1000,
      },
    ],
    status: "NEEDS_REVIEW",
  },

  {
    recordId: "rec-010",
    bolNumber: "1753617",
    contractLifting: "6201264",
    origin: "Albany, NY",
    supplier: "Global",
    carrier: "Mirabito",
    transactionDate: "2026-09-17",
    destination: "New York",
    lineItems: [
      {
        lineItemId: 1,
        product: "ULSD One Clear",
        e3StockId: "UP",
        netGallons: 9927,
        grossGallons: 10003,
      },
    ],
    status: "OCR_COMPLETE",
  },
];