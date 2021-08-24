class ExoVideo(dict):
	def __init__(self, start=1, end=2, layer=1, group=1, overlay=1, camera=0, video={}, flip=0):
		dict.__init__(self, {
				'start': start,
				'end': end,
				'layer': layer,
				'group': group,
				'overlay': overlay,
				'camera': camera,
				'sceneSettings': video,
				'effects': [
					{
						'_name': '反转',
						'上下翻转': 0,
						'左右翻转': flip,
						'亮度反转': 0,
						'色相反转': 0,
						'透明度反转': 0
					},
					{
						'_name': '标准变换',
						'X': 0.0,
						'Y': 0.0,
						'Z': 0.0,
						'缩放率': 100.00,
						'透明度': 0.0,
						'旋转': 0.00,
						'blend': 0,
					}
				]
			})
class SceneSettings(dict):
	def __init__(self, file, alpha=0, playback=1, vplay=100.0, loop=0):
		dict.__init__(self, {
			'_name': '视频文件',
			'播放位置': playback,
			'播放速度': vplay,
			'循环播放': loop,
			'读取Alpha通道': alpha,
			'file': file,
		})