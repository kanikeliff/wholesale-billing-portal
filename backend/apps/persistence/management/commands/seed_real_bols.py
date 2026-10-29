from django.core.management.base import BaseCommand

from apps.billing.models import BillingRecord
from application.services.ocr_processing_service import OCRProcessingService
from infrastructure.database.django_billing_record_repository import (
    DjangoBillingRecordRepository,
)
from infrastructure.ocr.bol_lab_adapter import BolLabAdapter


REAL_BOLS = [
    {
        "bol_number": "566836",
        "contract_number": None,
        "origin": "ETP Fullerton, PA terminal",
        "supplier": "Marathon",
        "carrier": "Penn Tank Lines",
        "transaction_date": "2026-09-17",
        "destination": "Pennsylvania",
        "products": [
            {
                "product": "B2 Diesel Clear",
                "product_code": None,
                "net_gallons": "7443",
                "gross_gallons": "7500",
                "e3_stock_id": "BD2",
            }
        ],
    },
    {
        "bol_number": "2569495",
        "contract_number": None,
        "origin": "Shell Providence, RI terminal",
        "supplier": "Sunoco",
        "carrier": "Dennis K. Burke Inc.",
        "transaction_date": "2026-09-15",
        "destination": "Massachusetts",
        "products": [
            {
                "product": "NRLM",
                "product_code": None,
                "net_gallons": "5971",
                "gross_gallons": "6000",
                "e3_stock_id": "ND",
            }
        ],
    },
    {
        "bol_number": "813492",
        "contract_number": None,
        "origin": "New Haven, CT",
        "supplier": "Valero",
        "carrier": "JP Noonan",
        "transaction_date": "2026-09-18",
        "destination": "Connecticut",
        "products": [
            {
                "product": "ULSD",
                "product_code": None,
                "net_gallons": "6939",
                "gross_gallons": "7000",
                "e3_stock_id": "UD",
            }
        ],
    },
    {
        "bol_number": "867187",
        "contract_number": "I 43117-3",
        "origin": "Vestal, NY",
        "supplier": "Buckeye",
        "carrier": "Munroe Tank Lines",
        "transaction_date": "2026-09-18",
        "destination": "New York",
        "products": [
            {
                "product": "87 gas",
                "product_code": None,
                "net_gallons": "6965",
                "gross_gallons": "7000",
                "e3_stock_id": "UX",
            },
            {
                "product": "93 gas",
                "product_code": None,
                "net_gallons": "2392",
                "gross_gallons": "2400",
                "e3_stock_id": "SX",
            },
        ],
    },
    {
        "bol_number": "239680",
        "contract_number": "224009",
        "origin": "Glenmont, NY",
        "supplier": "Citgo (FPA)",
        "carrier": "Mirabito",
        "transaction_date": "2026-09-17",
        "destination": "New York",
        "products": [
            {
                "product": "ULSD",
                "product_code": None,
                "net_gallons": "2984",
                "gross_gallons": "3000",
                "e3_stock_id": "UD",
            }
        ],
    },
    {
        "bol_number": "239681",
        "contract_number": "327897",
        "origin": "New York",
        "supplier": "Citgo (BP)",
        "carrier": "Mirabito",
        "transaction_date": "2026-09-17",
        "destination": "New York",
        "products": [
            {
                "product": "87 gas",
                "product_code": None,
                "net_gallons": "5555",
                "gross_gallons": "5596",
                "e3_stock_id": "UX",
            }
        ],
    },
    {
        "bol_number": "1996150",
        "contract_number": "40902",
        "origin": "Pennsylvania",
        "supplier": "PBF",
        "carrier": "Mirabito",
        "transaction_date": "2026-09-17",
        "destination": "Pennsylvania",
        "products": [
            {
                "product": "87 gas",
                "product_code": None,
                "net_gallons": "6456",
                "gross_gallons": "6500",
                "e3_stock_id": "UX",
            },
            {
                "product": "93 gas",
                "product_code": None,
                "net_gallons": "1495",
                "gross_gallons": "1500",
                "e3_stock_id": "SX",
            },
        ],
    },
    {
        "bol_number": "868375",
        "contract_number": "153",
        "origin": "Brewerton, NY",
        "supplier": "Mieco",
        "carrier": "Mirabito",
        "transaction_date": "2026-09-17",
        "destination": "New York",
        "products": [
            {
                "product": "ULSD",
                "product_code": None,
                "net_gallons": "7972",
                "gross_gallons": "8000",
                "e3_stock_id": "UD",
            }
        ],
    },
    {
        "bol_number": "831062",
        "contract_number": "2345",
        "origin": "Syracuse, NY",
        "supplier": "Monroe",
        "carrier": "Mirabito",
        "transaction_date": "2026-09-17",
        "destination": "New York",
        "products": [
            {
                "product": "87 gas",
                "product_code": None,
                "net_gallons": "7473",
                "gross_gallons": "7500",
                "e3_stock_id": "UX",
            },
            {
                "product": "93 gas",
                "product_code": None,
                "net_gallons": "990",
                "gross_gallons": "1000",
                "e3_stock_id": "SX",
            },
        ],
    },
    {
        "bol_number": "1753617",
        "contract_number": "6201264",
        "origin": "Albany, NY",
        "supplier": "Global",
        "carrier": "Mirabito",
        "transaction_date": "2026-09-17",
        "destination": "New York",
        "products": [
            {
                "product": "ULSD One Clear",
                "product_code": None,
                "net_gallons": "9927",
                "gross_gallons": "10003",
                "e3_stock_id": "UP",
            }
        ],
    },
]


class Command(BaseCommand):
    help = "Seed PostgreSQL with real annotated BOL development records."

    def handle(self, *args, **options):
        service = OCRProcessingService(
            adapter=BolLabAdapter(),
            billing_record_repository=DjangoBillingRecordRepository(),
        )

        created = 0
        skipped = 0

        for extraction in REAL_BOLS:
            bol_number = extraction["bol_number"]

            if BillingRecord.objects.filter(
                bol_number=bol_number
            ).exists():
                self.stdout.write(
                    self.style.WARNING(
                        f"SKIPPED BOL {bol_number}: already exists"
                    )
                )
                skipped += 1
                continue

            result = service.persist_extraction(extraction)

            self.stdout.write(
                self.style.SUCCESS(
                    f"CREATED BOL {bol_number} | "
                    f"recordId={result['recordId']} | "
                    f"status={result['status']}"
                )
            )
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. created={created}, skipped={skipped}"
            )
        )
