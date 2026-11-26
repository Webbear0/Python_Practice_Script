<template>
  <view class="page">
    <!-- 顶栏 -->
    <view class="header" :style="{ paddingTop: statusBarHeight + 'px' }">
      <text class="header-title">我的</text>
    </view>

    <!-- 账号信息卡片 -->
    <view class="card user-card">
      <view class="avatar">
        <text class="avatar-text">{{ (username || 'A')[0].toUpperCase() }}</text>
      </view>
      <view class="user-info">
        <text class="user-name">{{ username || '未登录' }}</text>
        <text class="user-role">系统管理员</text>
      </view>
    </view>

    <!-- 网关信息 -->
    <view class="card">
      <view class="cell" @click="showEditGateway">
        <text class="cell-label">网关地址</text>
        <text class="cell-value">{{ gateway || '未配置' }}</text>
        <text class="cell-arrow">></text>
      </view>
    </view>

    <!-- 操作选项 -->
    <view class="card">
      <view class="cell" @click="clearCache">
        <text class="cell-label">清除本地缓存</text>
        <text class="cell-arrow">></text>
      </view>
    </view>

    <!-- 退出按钮 -->
    <view class="logout-btn" @click="confirmLogout">
      <text class="logout-text">退出登录</text>
    </view>

    <!-- 修改网关弹窗 -->
    <view class="mask" v-if="showGatewayEdit" @click.self="showGatewayEdit = false">
      <view class="edit-box">
        <text class="edit-title">修改网关地址</text>
        <input class="edit-input" v-model="gatewayInput"
               placeholder="输入域名或 IP" />
        <view class="edit-btns">
          <text class="btn btn-cancel" @click="showGatewayEdit = false">取消</text>
          <text class="btn btn-save" @click="saveGateway">保存</text>
        </view>
      </view>
    </view>

    <!-- 底部安全区占位 -->
    <view style="height: 120rpx;"></view>
  </view>
</template>

<script>
export default {
  data() {
    return {
      statusBarHeight: 0,
      username: '',
      gateway: '',
      gatewayInput: '',
      showGatewayEdit: false
    }
  },
  onLoad() {
    this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 0
  },
  onShow() {
    this.username = uni.getStorageSync('ops_username') || ''
    this.gateway = uni.getStorageSync('ops_gateway') || ''
  },
  methods: {
    showEditGateway() {
      this.gatewayInput = this.gateway
      this.showGatewayEdit = true
    },

    saveGateway() {
      let gw = this.gatewayInput.trim()
      if (!gw) return uni.showToast({ title: '请输入地址', icon: 'none' })
      if (!/^https?:\/\//.test(gw)) gw = 'http://' + gw
      gw = gw.replace(/\/+$/, '')
      uni.setStorageSync('ops_gateway', gw)
      this.gateway = gw
      this.showGatewayEdit = false
      uni.showToast({ title: '网关地址已更新', icon: 'success' })
    },

    clearCache() {
      uni.showModal({
        title: '确认清除',
        content: '将清除所有本地缓存数据, 需要重新登录',
        success: (res) => {
          if (res.confirm) {
            uni.clearStorageSync()
            uni.showToast({ title: '缓存已清除', icon: 'success' })
            setTimeout(() => uni.reLaunch({ url: '/pages/login/login' }), 1000)
          }
        }
      })
    },

    confirmLogout() {
      uni.showModal({
        title: '确认退出',
        content: '确定要退出登录吗?',
        success: (res) => {
          if (res.confirm) {
            uni.removeStorageSync('ops_token')
            uni.removeStorageSync('ops_username')
            uni.showToast({ title: '已退出', icon: 'success' })
            setTimeout(() => uni.reLaunch({ url: '/pages/login/login' }), 500)
          }
        }
      })
    }
  }
}
</script>

<style>
.page { background: #f0f2f5; min-height: 100vh; }

/* 顶栏 */
.header { background: #1f2937; padding: 24rpx 30rpx; }
.header-title { color: #fff; font-size: 34rpx; font-weight: 600; }

/* 卡片 */
.card { background: #fff; margin: 20rpx 24rpx 0; border-radius: 16rpx;
        overflow: hidden; box-shadow: 0 2rpx 8rpx rgba(0,0,0,.06); }

/* 用户信息 */
.user-card { display: flex; align-items: center; padding: 36rpx 28rpx; }
.avatar { width: 88rpx; height: 88rpx; border-radius: 50%; background: #3b82f6;
          display: flex; align-items: center; justify-content: center; margin-right: 24rpx; }
.avatar-text { color: #fff; font-size: 36rpx; font-weight: 700; }
.user-info { flex: 1; }
.user-name { display: block; font-size: 32rpx; font-weight: 600; color: #1f2937; }
.user-role { display: block; font-size: 24rpx; color: #9ca3af; margin-top: 4rpx; }

/* 单元格 */
.cell { display: flex; align-items: center; padding: 28rpx; }
.cell-label { flex: 1; font-size: 28rpx; color: #1f2937; }
.cell-value { font-size: 24rpx; color: #9ca3af; margin-right: 8rpx;
              max-width: 400rpx; overflow: hidden; text-overflow: ellipsis; }
.cell-arrow { color: #d1d5db; font-size: 28rpx; }

/* 退出按钮 */
.logout-btn { margin: 40rpx 24rpx 0; background: #fff; border-radius: 16rpx;
              padding: 26rpx 0; text-align: center;
              box-shadow: 0 2rpx 8rpx rgba(0,0,0,.06); }
.logout-text { color: #dc2626; font-size: 30rpx; font-weight: 500; }

/* 修改网关弹窗 */
.mask { position: fixed; top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0,0,0,.5); display: flex; align-items: center;
        justify-content: center; z-index: 999; }
.edit-box { background: #fff; border-radius: 16rpx; padding: 40rpx; width: 600rpx; }
.edit-title { font-size: 32rpx; font-weight: 600; display: block;
              margin-bottom: 24rpx; color: #1f2937; }
.edit-input { border: 1px solid #d1d5db; border-radius: 8rpx;
              padding: 16rpx 20rpx; font-size: 28rpx; width: 100%; }
.edit-btns { display: flex; justify-content: flex-end; gap: 16rpx; margin-top: 30rpx; }
.btn { display: inline-block; padding: 14rpx 32rpx; border-radius: 8rpx;
       font-size: 26rpx; text-align: center; }
.btn-cancel { background: #f3f4f6; color: #374151; }
.btn-save   { background: #3b82f6; color: #fff; }
</style>
