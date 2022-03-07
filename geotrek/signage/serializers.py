import csv

from drf_dynamic_fields import DynamicFieldsMixin

from geotrek.authent.serializers import StructureSerializer
from geotrek.common.serializers import PictogramSerializerMixin, BasePublishableSerializerMixin
from geotrek.signage import models as signage_models

from mapentity.serializers.commasv import CSVSerializer
from mapentity.serializers.shapefile import ZipShapeSerializer

from rest_framework import serializers as rest_serializers
from rest_framework_gis import fields as rest_gis_fields
from rest_framework_gis.serializers import GeoFeatureModelSerializer


class SignageTypeSerializer(PictogramSerializerMixin):
    class Meta:
        model = signage_models.SignageType
        fields = ('id', 'pictogram', 'label')


class SignageSerializer(DynamicFieldsMixin, BasePublishableSerializerMixin, rest_serializers.ModelSerializer):
    structure = serializers.SlugRelatedField('name', read_only=True)
    type = serializers.SlugRelatedField('label', read_only=True)
    condition = serializers.SlugRelatedField('label', read_only=True)
    manager = serializers.SlugRelatedField('organism', read_only=True)
    sealing = serializers.SlugRelatedField('label', read_only=True)

    class Meta:
        model = signage_models.Signage
        fields = ('id', 'structure', 'name', 'description', 'type', 'code', 'printed_elevation', 'condition', 'uuid',
                  'manager', 'sealing', 'date_update', 'date_insert', 'implantation_year', 'coordinates') + \
            BasePublishableSerializerMixin.Meta.fields


class SignageRandoV2GeojsonSerializer(GeoFeatureModelSerializer, BasePublishableSerializerMixin):
    type = SignageTypeSerializer()
    structure = StructureSerializer()
    api_geom = rest_gis_fields.GeometryField(read_only=True, precision=7)

    class Meta(SignageSerializer.Meta):
        model = signage_models.Signage
        geo_field = 'api_geom'
        id_field = 'id'
        fields = ('id', 'structure', 'name', 'type', 'code', 'printed_elevation', 'condition',
                  'manager', 'sealing', 'api_geom', ) + BasePublishableSerializerMixin.Meta.fields


class BladeTypeSerializer(rest_serializers.ModelSerializer):
    class Meta:
        model = signage_models.BladeType
        fields = ('label', )


class BladeSerializer(rest_serializers.ModelSerializer):
    type = serializers.SlugRelatedField('label', read_only=True)
    direction = serializers.SlugRelatedField('label', read_only=True)
    color = serializers.SlugRelatedField('label', read_only=True)
    condition = serializers.SlugRelatedField('label', read_only=True)

    class Meta:
        model = signage_models.Blade
        fields = ('id', 'structure', 'number', 'order_lines', 'type', 'color', 'condition', 'direction')


class BladeGeojsonSerializer(GeoFeatureModelSerializer):
    type = BladeTypeSerializer()
    structure = StructureSerializer()
    order_lines = rest_serializers.SerializerMethodField()
    api_geom = rest_gis_fields.GeometryField(read_only=True, precision=7)

    def get_order_lines(self, obj):
        return obj.order_lines.values_list('pk', flat=True)

    class Meta(BladeSerializer.Meta):
        geo_field = 'api_geom'
        id_field = 'id'
        fields = BladeSerializer.Meta.fields + ('api_geom', )


class CSVBladeSerializer(CSVSerializer):
    def serialize(self, queryset, **options):
        """
        Uses self.columns, containing fieldnames to produce the CSV.
        The header of the csv is made of the verbose name of each field.
        """
        model_blade = signage_models.Blade
        columns = options.pop('fields')
        columns_lines = options.pop('line_fields')
        model_line = signage_models.Line
        stream = options.pop('stream')
        ascii = options.get('ensure_ascii', True)
        max_lines = max([value.lines.count() for value in queryset])

        header = self.get_csv_header(columns, model_blade)

        header_line = self.get_csv_header(columns_lines, model_line)

        for i in range(max_lines):
            numbered_header_lines = ['%s %s' % (header, i + 1) for header in header_line]
            header.extend(numbered_header_lines)

        getters = self.getters_csv(columns, model_blade, ascii)

        getters_lines = self.getters_csv(columns_lines, model_line, ascii)

        def get_lines():
            yield header
            for blade in queryset.order_by('signage__code', 'number'):
                column_getter = [getters[field](blade, field) for field in columns]
                for obj in blade.lines.order_by('number'):
                    column_getter.extend(getters_lines[field](obj, field) for field in columns_lines)
                yield column_getter

        writer = csv.writer(stream)
        writer.writerows(get_lines())


class ZipBladeShapeSerializer(ZipShapeSerializer):
    def split_bygeom(self, iterable, geom_getter=lambda x: x.geom):
        lines = [blade for blade in iterable]
        return super().split_bygeom(lines, geom_getter)
