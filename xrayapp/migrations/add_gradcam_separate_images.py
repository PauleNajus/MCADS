from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('xrayapp', '0011_merge_20250516_1309'),
    ]

    operations = [
        migrations.AddField(
            model_name='xrayimage',
            name='gradcam_heatmap',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='xrayimage',
            name='gradcam_overlay',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ] 