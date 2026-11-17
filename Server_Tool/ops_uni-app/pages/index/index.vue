<template>
  <view class="page">
    <!-- 顶栏 -->
    <view class="header">
      <text class="header-title">掌上运维</text>
      <text class="header-btn" @click="showConfig = true">设置</text>
    </view>

    <!-- 网关配置弹窗 -->
    <view class="mask" v-if="showConfig" @click.self="cancelConfig">
      <view class="config-box">
        <text class="config-title">网关地址配置</text>
        <input class="config-input" v-model="gatewayInput"
               placeholder="输入域名或 IP, 如 172.16.10.252" />
        <view class="config-btns">
          <text class="btn btn-cancel" @click="cancelConfig">取消</text>
          <text class="btn btn-save" @click="saveGateway">保存</text>
        </view>
      </view>
    </view>

    <!-- 加载 / 空状态 -->
    <view v-if="!gateway" class="empty">
      <text class="empty-text">请先点击右上角「设置」配置网关地址</text>
    </view>
    <view v-else-if="loading && servers.length === 0" class="empty">
      <text class="empty-text">加载中...</text>
    </view>
    <view v-else-if="servers.length === 0" class="empty">
      <text class="empty-text" @click="fetchStatus">暂无数据, 点击重试</text>
    </view>

    <!-- 服务器卡片列表 -->
    <view class="card" v-for="(s, i) in servers" :key="i">
      <view class="card-head">
        <text class="card-name">{{ s.hostname || s.ip }}</text>
        <text class="card-ip">{{ s.ip }}</text>
      </view>

      <!-- CPU -->
      <view class="metric">
        <text class="metric-label">CPU</text>
        <view class="bar-bg">
          <view class="bar-fill" :class="{ 'bar-warn': s.cpu > 80 }"
                :style="{ width: Math.min(s.cpu, 100) + '%' }"></view>
        </view>
        <text class="metric-val" :class="{ 'val-warn': s.cpu > 80 }">{{ s.cpu.toFixed(1) }}%</text>
      </view>

      <!-- 内存 -->
      <view class="metric">
        <text class="metric-label">内存</text>
        <view class="bar-bg">
          <view class="bar-fill" :class="{ 'bar-warn': s.mem > 80 }"
                :style="{ width: Math.min(s.mem, 100) + '%' }"></view>
        </view>
        <text class="metric-val" :class="{ 'val-warn': s.mem > 80 }">{{ s.mem.toFixed(1) }}%</text>
      </view>

      <!-- 磁盘 -->
      <view class="metric">
        <text class="metric-label">磁盘</text>
        <view class="bar-bg">
          <view class="bar-fill" :class="{ 'bar-warn': s.disk > 80 }"
                :style="{ width: Math.min(s.disk, 100) + '%' }"></view>
        </view>
        <text class="metric-val" :class="{ 'val-warn': s.disk > 80 }">{{ s.disk.toFixed(1) }}%</text>
      </view>

      <!-- 服务状态 -->
      <view class="svc-row">
        <text class="svc-label">服务状态:</text>
        <text class="svc-val">{{ s.services || '-' }}</text>
      </view>

      <!-- 采集时间 -->
      <view class="svc-row">
        <text class="svc-label">采集时间:</text>
        <text class="svc-time">{{ s.time }}</text>
      </view>

      <!-- 重启按钮 -->
      <view class="btn-row">
        <text class="btn btn-restart" v-for="svc in parseSvcNames(s.services)" :key="svc"
              @click="confirmRestart(s.ip, svc)">
          重启 {{ svc }}
        </text>
      </view>
    </view>

    <!-- 底部刷新按钮 -->
    <view class="refresh-row" v-if="gateway && servers.length > 0">
      <text class="btn btn-refresh" @click="fetchStatus">刷新数据</text>
    </view>
  </view>
</template>

<script>
export default {
  data() {
    return {
      gateway: '',
      gatewayInput: '',
      showConfig: false,
      servers: [],
      loading: false
    }
  },
  onLoad() {
    const saved = uni.getStorageSync('ops_gateway')
    if (saved) {
      this.gateway = saved
      this.fetchStatus()
    } else {
      this.showConfig = true
    }
  },
  methods: {
    // 保存网关地址
    saveGateway() {
      let gw = this.gatewayInput.trim()
      if (!gw) return uni.showToast({ title: '请输入地址', icon: 'none' })
      // 自动补全协议头
      if (!/^https?:\/\//.test(gw)) gw = 'http://' + gw
      // 去除末尾斜杠
      gw = gw.replace(/\/+$/, '')
      this.gateway = gw
      uni.setStorageSync('ops_gateway', gw)
      this.showConfig = false
      this.fetchStatus()
      uni.showToast({ title: '已保存', icon: 'success' })
    },

    cancelConfig() {
      if (this.gateway) this.showConfig = false
    },

    // 查询监控数据
    fetchStatus() {
      this.loading = true
      uni.request({
        url: this.gateway + '/api/status',
        method: 'GET',
        success: (res) => {
          if (Array.isArray(res.data)) {
            this.servers = res.data
          } else if (res.data && res.data.error) {
            uni.showToast({ title: res.data.error, icon: 'none' })
          }
        },
        fail: (err) => {
          uni.showToast({ title: '连接失败, 请检查网关地址', icon: 'none', duration: 2000 })
        },
        complete: () => { this.loading = false }
      })
    },

    // 从服务状态字符串中解析服务名列表
    // 输入: "apache2=active, mariadb=active"  输出: ["apache2", "mariadb"]
    parseSvcNames(svcStr) {
      if (!svcStr || svcStr === '-') return []
      return svcStr.split(',').map(s => s.trim().split('=')[0]).filter(Boolean)
    },

    // 确认重启弹窗
    confirmRestart(ip, service) {
      uni.showModal({
        title: '确认重启',
        content: `确定要重启 ${ip} 上的 ${service} 服务吗?`,
        success: (res) => {
          if (res.confirm) this.doRestart(ip, service)
        }
      })
    },

    // 执行远程重启
    doRestart(ip, service) {
      uni.showLoading({ title: '正在重启...', mask: true })
      uni.request({
        url: this.gateway + '/api/restart',
        method: 'POST',
        header: { 'Content-Type': 'application/json' },
        data: { ip, service },
        success: (res) => {
          const d = res.data || {}
          uni.showToast({
            title: d.message || (d.success ? '重启成功' : '重启失败'),
            icon: d.success ? 'success' : 'none',
            duration: 2000
          })
          // 重启后延迟刷新状态
          if (d.success) setTimeout(() => this.fetchStatus(), 3000)
        },
        fail: () => {
          uni.showToast({ title: '请求失败', icon: 'none' })
        },
        complete: () => { uni.hideLoading() }
      })
    }
  }
}
</script>

<style>
.page { background: #f0f2f5; min-height: 100vh; padding-bottom: 30rpx; }

/* 顶栏 */
.header { background: #1f2937; display: flex; justify-content: space-between;
          align-items: center; padding: 24rpx 30rpx; }
.header-title { color: #fff; font-size: 34rpx; font-weight: 600; }
.header-btn { color: #60a5fa; font-size: 28rpx; }

/* 网关配置弹窗 */
.mask { position: fixed; top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0,0,0,.5); display: flex; align-items: center;
        justify-content: center; z-index: 999; }
.config-box { background: #fff; border-radius: 16rpx; padding: 40rpx;
              width: 600rpx; }
.config-title { font-size: 32rpx; font-weight: 600; display: block;
                margin-bottom: 24rpx; color: #1f2937; }
.config-input { border: 1px solid #d1d5db; border-radius: 8rpx;
                padding: 16rpx 20rpx; font-size: 28rpx; width: 100%; }
.config-btns { display: flex; justify-content: flex-end; gap: 16rpx; margin-top: 30rpx; }

/* 通用按钮 */
.btn { display: inline-block; padding: 14rpx 32rpx; border-radius: 8rpx;
       font-size: 26rpx; text-align: center; }
.btn-cancel { background: #f3f4f6; color: #374151; }
.btn-save   { background: #3b82f6; color: #fff; }

/* 卡片 */
.card { background: #fff; margin: 20rpx 24rpx 0; border-radius: 16rpx;
        padding: 28rpx; box-shadow: 0 2rpx 8rpx rgba(0,0,0,.06); }
.card-head { display: flex; justify-content: space-between; align-items: center;
             margin-bottom: 20rpx; }
.card-name { font-size: 32rpx; font-weight: 600; color: #1f2937; }
.card-ip   { font-size: 24rpx; color: #9ca3af; }

/* 指标行 */
.metric { display: flex; align-items: center; margin-bottom: 14rpx; }
.metric-label { width: 80rpx; font-size: 24rpx; color: #6b7280; }
.bar-bg { flex: 1; height: 20rpx; background: #e5e7eb; border-radius: 10rpx;
          overflow: hidden; margin: 0 16rpx; }
.bar-fill { height: 100%; background: #22c55e; border-radius: 10rpx;
            transition: width .3s; }
.bar-warn { background: #ef4444; }
.metric-val { width: 100rpx; text-align: right; font-size: 24rpx; color: #374151;
              font-weight: 600; }
.val-warn { color: #ef4444; }

/* 服务状态 */
.svc-row { display: flex; margin-top: 10rpx; font-size: 24rpx; }
.svc-label { color: #6b7280; margin-right: 8rpx; }
.svc-val  { color: #374151; flex: 1; }
.svc-time { color: #9ca3af; }

/* 重启按钮行 */
.btn-row { display: flex; gap: 16rpx; margin-top: 20rpx; flex-wrap: wrap; }
.btn-restart { background: #fee2e2; color: #dc2626; font-size: 24rpx;
               padding: 12rpx 28rpx; border-radius: 8rpx; }

/* 刷新 */
.refresh-row { display: flex; justify-content: center; margin-top: 30rpx; }
.btn-refresh { background: #3b82f6; color: #fff; padding: 18rpx 60rpx;
               border-radius: 10rpx; font-size: 28rpx; }

/* 空状态 */
.empty { display: flex; justify-content: center; align-items: center;
         height: 400rpx; }
.empty-text { font-size: 28rpx; color: #9ca3af; }
</style>
