from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Location, Report, Review


class ReviewInline(admin.TabularInline):
    model = Review
    extra = 0
    readonly_fields = ('created_at',)


class ReportInline(admin.TabularInline):
    model = Report
    extra = 0
    readonly_fields = ('created_at',)


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('building_name', 'address', 'source', 'status', 'review_summary', 'pending_reports')
    list_filter = ('status', 'source')
    list_editable = ('status',)
    search_fields = ('building_name', 'address', 'detail_text')
    readonly_fields = ('created_at', 'photo_preview')
    inlines = [ReviewInline, ReportInline]
    actions = ['mark_removed', 'mark_confirmed']

    @admin.display(description='리뷰 (👍/👎)')
    def review_summary(self, obj):
        up = obj.reviews.filter(type=Review.Type.UP).count()
        down = obj.reviews.filter(type=Review.Type.DOWN).count()
        return f'👍 {up} / 👎 {down}'

    @admin.display(description='미처리 신고')
    def pending_reports(self, obj):
        count = obj.reports.filter(status=Report.Status.PENDING).count()
        return f'⚠️ {count}' if count else '-'

    @admin.display(description='사진 미리보기')
    def photo_preview(self, obj):
        if not obj.photo:
            return '(사진 없음)'
        return format_html('<img src="{}" style="max-height:300px;" />', obj.photo.url)

    @admin.action(description='선택한 위치를 삭제됨(removed)으로 변경')
    def mark_removed(self, request, queryset):
        updated = queryset.update(status=Location.Status.REMOVED)
        self.message_user(request, f'{updated}개 위치를 삭제됨 처리했습니다.')

    @admin.action(description='선택한 위치를 확인됨(confirmed)으로 변경')
    def mark_confirmed(self, request, queryset):
        updated = queryset.update(status=Location.Status.CONFIRMED)
        self.message_user(request, f'{updated}개 위치를 확인됨 처리했습니다.')


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('location', 'type', 'tags', 'free_text', 'created_at')
    list_filter = ('type', 'created_at')
    search_fields = ('location__building_name', 'free_text')
    readonly_fields = ('created_at',)


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    """앱의 '관리자 신고목록 화면'을 대체하는 관리 페이지."""

    list_display = ('location_link', 'location_status', 'reason', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    list_editable = ('status',)
    search_fields = ('location__building_name', 'reason')
    readonly_fields = ('created_at',)
    actions = ['remove_location', 'mark_resolved']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('location')

    @admin.display(description='신고된 위치')
    def location_link(self, obj):
        url = reverse('admin:locations_location_change', args=[obj.location_id])
        return format_html('<a href="{}">{}</a>', url, obj.location.building_name)

    @admin.display(description='위치 상태')
    def location_status(self, obj):
        return obj.location.get_status_display()

    @admin.action(description='신고된 위치를 삭제됨 처리하고 신고를 처리완료로 변경')
    def remove_location(self, request, queryset):
        location_ids = set(queryset.values_list('location_id', flat=True))
        Location.objects.filter(id__in=location_ids).update(status=Location.Status.REMOVED)
        updated = queryset.update(status=Report.Status.RESOLVED)
        self.message_user(
            request,
            f'{len(location_ids)}개 위치를 삭제됨 처리하고 신고 {updated}건을 처리완료로 바꿨습니다.',
        )

    @admin.action(description='신고만 처리완료로 변경 (위치는 유지)')
    def mark_resolved(self, request, queryset):
        updated = queryset.update(status=Report.Status.RESOLVED)
        self.message_user(request, f'신고 {updated}건을 처리완료로 바꿨습니다.')


admin.site.site_header = 'CupPit 관리자'
admin.site.site_title = 'CupPit Admin'
admin.site.index_title = '세척기 위치 · 리뷰 · 신고 관리'
