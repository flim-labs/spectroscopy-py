import os
import struct

import matplotlib.pyplot as plt
import numpy as np

arr = np.array(
    [24148, 24145, 24174, 23900, 24223, 23815, 23583, 23864, 23665, 23366, 23493, 23136, 23445, 23233, 23144, 23074,
     23371, 23158, 22716, 22721, 22795, 22627, 22750, 22487, 22749, 22384, 22256, 22755, 22144, 22240, 22315, 22025,
     21846, 21918, 22111, 21731, 21946, 21785, 21836, 21608, 21352, 21654, 21511, 21312, 21456, 21419, 21025, 21119,
     20941, 20739, 20879, 20963, 20647, 20981, 20631, 20550, 20515, 20681, 20582, 20136, 20286, 20532, 20110, 20280,
     20330, 20317, 20108, 19994, 20144, 19961, 19907, 19822, 19827, 19686, 19657, 19732, 19685, 19535, 19518, 19625,
     19422, 19524, 19387, 19544, 19488, 19230, 19168, 19025, 18960, 19139, 19192, 19066, 19106, 19072, 19026, 18685,
     19010, 18738, 18685, 18785, 18882, 18741, 18767, 18502, 18530, 18614, 18654, 18569, 18428, 18492, 18351, 18694,
     18356, 18230, 18292, 18186, 18206, 18187, 17988, 18239, 18142, 18116, 18260, 18309, 18038, 18337, 18030, 18029,
     18031, 18046, 18141, 18092, 18141, 17889, 18048, 17737, 18030, 17642, 17701, 17784, 17839, 17877, 17670, 17677,
     17552, 17818, 17669, 17540, 17541, 17563, 17778, 17800, 17436, 17524, 17462, 17485, 17445, 17585, 17638, 18280,
     18517, 19099, 20009, 20550, 21312, 22193, 23021, 23390, 24455, 25516, 26255, 27024, 28251, 28782, 29370, 29984,
     30291, 30277, 30534, 30796, 30735, 30673, 30760, 30634, 30343, 30671, 30204, 30210, 30460, 30199, 29987, 29870,
     29927, 29684, 29583, 29822, 29708, 29920, 29538, 29293, 29409, 29346, 29226, 29174, 29037, 29129, 29043, 28968,
     28791, 28554, 28823, 28650, 28579, 28357, 28363, 28156, 28110, 28008, 27541, 28003, 27820, 27551, 28053, 27172,
     27300, 27088, 27058, 27127, 26974, 26953, 26995, 26687, 26515, 26902, 26337, 26315, 26116, 26149, 26112, 25814,
     25828, 25811, 25839, 25348, 25451, 25374, 25495, 25111, 24773, 24634, 24713, 24790, 24701, 24629, 24482, 24260]
)
print(len(arr))
# shift array by 160
arr = np.roll(arr, -160)

plt.xlabel("Bin")
plt.ylabel("Intensity")
plt.title("Spectroscopy")

plt.ylim(0, max(arr) * 1.1)

plt.plot(arr, label="Channel 1")

plt.legend()
plt.show()
