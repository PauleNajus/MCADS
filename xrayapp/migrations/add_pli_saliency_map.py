from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('xrayapp', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='xrayimage',
            name='pli_saliency_map',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ] 