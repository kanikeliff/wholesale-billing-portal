from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0002_billingrecord_b_rec_bol_idx_and_more"),
        ("persistence", "0002_ocrjob"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="document",
            index=models.Index(
                fields=["billing_record", "-created_at"],
                name="p_doc_rec_time_idx",
            ),
        ),
    ]
