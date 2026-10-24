"""Bước 6: Chuyển văn bản thành giọng nói (TTS)."""
import os
os.environ["HF_HOME"] = r"D:\Auto-video-builder\data\hf_cache"
os.environ["VIENEU_HOME"] = r"D:\Auto-video-builder\data\vieneu_cache"
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
import os
import subprocess
import yaml
import re
from backend.media_info import get_video_duration

# Import Edge-TTS (giọng cũ)
try:
    import edge_tts
except ImportError:
    edge_tts = None

# Import KorvaTTS
try:
    from korvatts import TTS as KorvaTTS
    _korva_tts = None
    HAS_KORVA = True
except ImportError:
    HAS_KORVA = False

# Import VieNeu-TTS (để clone giọng)
try:
    from vieneu import Vieneu
    _vieneu_tts = None
    HAS_VIENEU = True
except ImportError:
    HAS_VIENEU = False

# Đường dẫn tới file giọng mẫu của bạn
REF_AUDIO_PATH = "Ngọc huyền.mp3" 
# BẮT BUỘC: Bạn phải điền chính xác nội dung file mp3 đó đang nói gì vào đây
REF_TEXT = "Tôi mất 10 năm để đưa người đàn ông mình yêu lên chiếc ghế cao nhất. Ngày anh thật sự có được tất cả, tôi ngồi dưới sân khấu chờ anh công khai mối quan hệ của chúng tôi. Nhưng người được anh nắm tay bước lên lại là một người phụ nữ khác. Tôi vẫn vỗ tay như tất cả mọi người. Bởi khi ấy tôi đã quyết định, những gì tôi có thể đưa anh lên được, tôi cũng có thể tự tay lấy lại. Tôi tên Tống Nhược Vi, nếu phải chọn một điều tôi giỏi nhất trong 32 năm đầu đời, có lẽ không phải kinh doanh, cũng chẳng phải nhìn người, mà là giả vờ mình không cần bất cứ thứ gì. Tôi sinh ra trong Tống gia, một gia đình đủ giàu để người ngoài nghĩ tất cả con cháu trong nhà đều sống sung sướng. Nhưng một gia đình càng có nhiều thứ để chia, người ta càng phân biệt xem ai đáng được nhận nhiều hơn. Cha tôi là con thứ 2, không giỏi kinh doanh, cả đời chỉ giữ một chức vụ không cao không thấp trong tập đoàn. Mẹ tôi mất khi tôi 13 tuổi, từ đó tôi sống phần lớn thời gian ở nhà ông nội cùng gia đình bác cả. Con gái bác là Tống Minh Hạ, hơn tôi 1 tuổi. Minh Hạ đẹp từ nhỏ, thông minh, nói chuyện thẳng thắn, đi đến đâu cũng có người chú ý. Ông nội thích chị ấy, các cô chú thích chị ấy, ngay cả người giúp việc trong nhà khi mang trái cây lên cũng thường đặt đĩa đẹp hơn trước mặt chị ấy. Không ai cố tình bạc đãi tôi, đó mới là điều khiến sự khác biệt trở nên khó nói. Nếu có ai đánh tôi, mắng tôi, tôi còn có thể giận. Như họ vẫn cho tôi ăn, cho tôi học trường tốt, vẫn nhớ sinh nhật tôi, chỉ là mọi thứ dành cho tôi luôn ít hơn một chút. Minh Hạ được hỏi muốn học trường nào, tôi được bảo học cùng trường với chị cho tiện. Minh Hạ muốn phòng hướng nam, tôi lập tức được dặn đổi phòng vì con ở đâu chẳng được. Minh Hạ muốn vào bộ phận chiến lược sau khi tốt nghiệp, ông nội nói con bé có có chí hướng. Tôi cũng muốn vào đó, cha chỉ bảo, con đừng tranh với chị. Dù sao sau này tập đoàn cũng do bác cả và Minh Hạ quản lý. Tôi không tranh, tôi luôn cười rồi nói được, 18 tuổi, tôi đã hiểu một điều, người không có quyền lựa chọn tốt nhất đừng để ai biết mình muốn gì. Bởi một khi người khác biết, họ sẽ có thêm một thứ để lấy khỏi tay mình. Tôi học cách nói con không sao, con không thích lắm, nhưng chị cũng được. Dần dần mọi người thật sự tin tôi là một đứa không có tham vọng. Chỉ có tôi biết mỗi lần nhiều một thứ, tôi đều nhớ rất rõ. Không phải để một ngày đòi lại, khi ấy tôi chưa nghĩ xa như vậy, tôi chỉ không muốn quên cảm giác của mình. Năm 22 tuổi, tôi gặp Trình Cảnh Thâm, Trình gia và Tống gia cùng đấu tư vào một dự án bất động sản. Hôm đó có tiệc ở khách sạn, tôi bị cha gọi đến chỉ để đủ mặt gia đình. Minh Hạ mới là người được ông nội đưa đi giới thiệu với các cổ đồng. Tôi ngồi gần cuối bàn, nghe người lớn nói chuyện, thi thoảng mình cười đúng lúc. Cảnh thâm đến muộn, anh 27 tuổi là con trai thứ 2 của Trình Trấn Đông. Người ngoài đều biết Trình gia có ba người con, nhưng gần như chẳng ai xem Cảnh Thâm là ứng viên kế nghiệp. Anh trai anh, Trình Cảnh Nghiêm là con của người vợ đầu đã mất, từ nhỏ đã được đưa theo trà học việc. Còn mẹ Cảnh Thâm từng là một nghệ sĩ piano của hôn nhân với Trình Trấn Đông chỉ kéo dài vài năm. Sau lì hôn, bà ra nước ngoài, Cảnh Thâm ở lại Trình gia nhưng chưa bao giờ thật sự được đặt vào trung tâm. Tôi chú ý đến anh vì anh giống tôi. Không phải về ngoài, mà là cách anh ngồi ở một chiếc bàn vốn thuộc về gia đình mình nhưng vẫn giống một vị khách. Trong bữa tiệc, Trình Trấn Đông giới thiệu Cảnh Nghiêm với gần như tất cả mọi người. Đến Cảnh Thâm, ông chỉ nói, con trai thứ 2 của tôi. Hết! Tôi nhìn thấy bàn tay anh đặt dưới bàn xét lại rồi thả ra. Không ai khác để ý. Tôi để ý vì tôi từng làm động tác ấy rất nhiều lần. Sau tiếc tôi ra ban công tránh ồn. Cảnh thâm đã đứng đó. Tôi định quay vào thì anh hỏi, cô cũng bị bỏ quên à. Tôi nhìn anh, anh cười, xin lỗi, nói hơi thẳng. Tôi đáp, tôi từng người bị bỏ quên không nên chủ động nhắc người khác nhớ đến mình. Anh im vài giây rối bật cười. Cô tên gì? Tống nhực vi. Tôi biết. Tôi hơi bất ngờ. Anh nói, em gái Tống Minh Hạ. Chỉ một câu thôi đã khiến tôi mất thiện cảm. Tôi nói, không phải em gái. Em họ. Cảnh thâm nhìn tôi rồi gật đầu, xin lỗi. Tống nhực vi. Anh gọi lại đúng tên tôi, không thêm bất kỳ quan hệ nào phía sau. Có lẽ từ khoảnh khác đó tôi bắt đầu nhớ anh. Chúng tôi gặp lại vài lần vì công việc. Cảnh thâm khi ấy phụ trách một công ty con gần như bị Trình gia bỏ mặc. Anh không bất tài. Ngược lại, anh giỏi đến mức tôi không hiểu tại sao Trình Trấn Đông không dùng anh. Sau này tôi mới biết không phải người tra ấy không nhìn thấy năng lực của con trai. Ông chỉ đã chọn người kế nghiệp từ rất lâu mà trong những gia đình như chúng tôi, đôi khi năng lực không quan trọng bằng việc ai được lựa chọn trước. Tôi hiểu cảm giác ấy qua rõ. Cảnh thâm cũng hiểu tôi. Anh là người đầu tiên nhận ra tôi không hề hiền như vậy ngoài. Một lần chúng tôi cùng tham dự cuộc họp, một quản lý lấy ý tưởng của tôi rồi trình bày như của ông ta. Tôi không phản ứng, còn mình cười ghi chép. Tàn học, Cảnh Thâm hỏi, không tức à. Tôi nói, có gì để tức. Anh đáp, em đã viết bản đề xuất đó. Tôi nhìn anh, anh biết. Tôi đọc bản nháp trước đó. Tôi cười, biết thì sao. Anh nói, nếu là tôi, tôi sẽ lấy lại. Tôi hỏi, nếu lấy lại ngay mà vẫn không được gì thì sao. Cảnh thâm im lặng. Tôi nói, tôi thích để người ta nợ mình lâu hơn một chút. Anh nhìn tôi rất lâu rồi nói, nhưng vì, em đang sợ hơn vài ngoài nhiều. Tôi hỏi, sợ không. Anh cười, chưa. Sau này tôi đã nghĩ về chữ trợ ấy rất nhiều. Chúng tôi bắt đầu yêu nhau vào một đêm cuối năm. Không có lời tỏ tình đẹp đẽ. Anh vừa thất bại trong một dự án vì cha chuyển nguồn vốn sang cho Cảnh Nghiêm. Tôi ngồi cùng anh trong văn phòng đến gần sáng. Cảnh thâm nhìn thành phố ngoài cử kính rồi hỏi, em có bao giờ muốn dành tất cả những thứ vốn không dành cho mình không? Tôi đáp, ngày nào cũng muốn. Anh quay lại. Tôi nói, chỉ là tôi không nói. Anh cười, lần đầu tiên tôi thấy một người hiểu mình mà không cần giải thích. Anh bảo, một ngày nào đó anh sẽ ngồi vào vị trí của cha. Tôi không cười anh. Tôi lấy tập hồ sơ trên bàn, mở ra rồi chỉ vào khoản đầu tư đang khiến công ty con của anh thua lỗ. Vậy trước hết anh giải quyết cái này đi. Cảnh thâm nhìn tôi rồi hỏi, em giúp anh. Tôi đáp, anh có gì để tôi giúp. Anh nói, chưa có gì. Tôi bảo, vậy sau này trả. Anh hỏi tôi muốn gì. Tôi nhìn anh rất lâu rồi nói, đến lúc đó em sẽ nghĩ. Đó là khởi đầu của 15 năm. Năm đầu tiên, tôi giúp Cảnh Thâm cứu công ty con. Tôi dùng quan hệ của Tống gia kết nối cho anh một nhà cung cấp mà Cảnh Nghiêm từng bỏ qua. Đổi lại, Cảnh Thâm giúp tôi lấy lại quyền tác giả của bản chiến lược từng bị người quản lý kia chiếm mất. Anh không công khai đứng ra bảo vệ tôi. Anh chỉ gửi đúng bản nháp có thời gian tạo file cho người cần thấy. Quả lý kia bị điều chuyển. Tôi lần đầu tiên được đưa vào nhóm dự án chính. Tôi hỏi tại sao giúp mình. Anh nói, em giúp anh trước. Tôi nói, vậy chúng ta hòa. Anh đáp, anh không muốn hòa. Tôi nhìn anh. Cảnh thâm nói, anh muốn nợ em lâu hơn một chút. Đó chính là câu tôi từng nói. Tôi đã cười rất lâu. Năm thứ 2, công ty anh bắt đầu có lãi. Năm thứ 3, Cảnh Thâm được gọi về trục sở. Năm thứ 4, anh dành được ghế trong hội đồng điều hành. Năm thứ 5, lần đầu tiên người ta đã nhắc tên anh Cảnh Nghiêm khi nói về người kế nghiệp. Không ai biết phía sau những bước ấy có bao nhiêu thứ liên quan đến tôi. Tôi biết những cổ đồng nào đang bất mãn với Cảnh Nghiêm vì tống gia từng làm việc với họ. Tôi biết một quỹ đầu tư đang muốn thoái vốn trước khi thị trường biết. Tôi biết người nào có thể được thuyết phục bằng lợi ích, người nào chỉ cần được tôn trọng. Có lần Cảnh Thâm hỏi, em lấy đâu ra nhiều thông tin vậy. Tôi nói, vì mọi người nói rất nhiều trước mặt một người mà họ cho rằng không quan trọng. Anh nhìn tôi rồi nói, may mà họ qua thường em. Tôi cười, em cũng thấy vậy. Chúng tôi yêu nhau trong bí mật. Không phải vì số hổ mà vì cả hai đều hiểu công khai quá sớm chỉ biến mối quan hệ thành một con bài cho hai gia đình. Tôi chưa bao giờ yêu cầu anh tặng những thứ đất tiền. Sinh nhật năm 26 tuổi, Cảnh Thâm hỏi tôi muốn gì. Tôi nói muốn một chiếc bánh hạt dẻ ở tiệm cách công ty gần 20 cây số. Anh mắng tôi phiền nhưng tôi vẫn mang đến. Chúng tôi ngồi trong văn phòng tối, dùng hai chiếc thìa như ăn hết cái bánh nhỏ. Tôi hỏi, nếu một ngày anh thật sự trở thành chủ tịch thì sao? Anh nói, thì mua luôn tiệp bánh cho em. Tôi bật cười, em hỏi chúng ta thì sao? Cảnh thâm im lặng vài giây rồi nói, đến lúc anh ngồi được vào vị trí đó, anh sẽ cho em một danh phận. Tôi hỏi, danh phận gì? Anh nhìn tôi, em muốn danh phận gì? Tôi không đáp. Anh nắm lấy tay tôi rồi nói, thứ em muốn. Tôi đã tin câu ấy suốt nhiều năm. Không phải vì tôi ngu ngốc. Cảnh thâm thật sự yêu tôi. Khi cha tôi phải nhập viện, anh bỏ một bữa tiệp quan trọng để đến. Khi ông nội lại do vị trí tôi muốn cho minh hạ, tôi ngồi trong xe không nói gì gần một tiếng, anh cũng không ép tôi phải ổn. Anh chỉ nói, có một ngày em sẽ không cần họ cho nữa. Khi tôi hỏi, nếu ngày ấy không đến thì sao? Anh đáp, anh cho em. Tôi nổi giận anh. Em không cần anh cho. Cảnh thâm lập tức sự, vậy anh đứng cạnh nhìn em tự lấy. Tôi mới hết dẫn. Anh hiểu tôi đến mức ấy. Tôi cũng hiểu anh. Cảnh thâm không chịu được cảm giác bị cha xem nhẹ. Anh có thể thức ba đêm để sự một phương án chỉ vì Cảnh Nghiêm từng nói anh không đủ kinh nghiệm. Anh nói mình muốn chiếc ghế chủ tịch vì muốn chứng minh năng lực. Tôi biết không hoàn toàn. Anh muốn cha thừa nhận đã nhìn sai. Giống như tôi muốn ông nội một ngày phải thừa nhận đứa cháu gái ông từng xem nhẹ không hề kém minh hạ. Có lẽ đó là lý do chúng tôi yêu nhau. Chúng tôi nhìn thấy vết thương của nhau và tưởng vì hiểu nó nên sẽ không bao giờ dùng nó làm đau nhau. Năm thứ 6, mọi thứ bắt đầu thay đổi. Cảnh nghiêm mắc sai lầm trong một thương vụ nước ngoài. Cảnh thâm muốn tận dụng cơ hội. Tôi giúp anh tìm được bằng chứng cho thấy nhóm của Cảnh Nghiêm đã bỏ qua cảnh báo rủi ro. Ban đầu tôi chỉ định đưa tài liệu cho Cảnh Thâm để anh bộ hội đồng xem set lại quyền hạn. Nhưng trước cuộc họp, tôi phát hiện ông nội tôi đang muốn dùng Tống gia hỗ trợ Cảnh Nghiêm đổi lấy một dự án chung. Nếu thành công, Cảnh Thâm sẽ lại bị đầy xuống. Tôi không nói với anh. Tôi tự mình gửi tài liệu trong một cuộc cộng đồng độc lập ngay trước cuộc họp. Cảnh nghiêm bị đình chỉ quyền điều hành dự án. Cảnh thâm được đưa lên thay. Tôi đó anh hỏi là em làm. Tôi nói phải. Anh hỏi tại sao không nói trước? Nếu nói, anh có đồng ý không? Cảnh thâm im lặng. Tôi cười, vậy nên em không nói. Anh không vui. Anh muốn thắng, nhưng không muốn em làm những chuyện này thay anh. Tôi hỏi, anh nghĩ mình đi đến hôm nay bằng cái gì? Cảnh thâm nhìn tôi. Tôi nói, anh chỉ cần giữ tay sạch vì có em làm những việc anh không muốn làm. Anh đổi dẫn lần đầu tiên. Anh bảo tôi đừng biến mọi thứ thành một cuộc chiến. Tôi hỏi, nếu không phải chiến tranh, tại sao người thua luôn là chúng ta? Anh không trả lời. Chúng tôi cãi nhau rồi 3 ngày không gặp. Đêm thứ tư, tôi về nhà thì thấy chiếc bánh hạt sẻ đặt chất cửa. Không có lời di lỗi, chỉ có mảnh giấy: Ăn đi rồi cãi tiếp. Tôi cầm chiếc bánh đứng ngoài cửa rất lâu. Tôi đã nghĩ, thấy chưa, dù mình làm gì anh vẫn hiểu. Đó là sai lầm đầu tiên của tôi. Tôi bắt đầu xem sự trở lại của anh như một điều hiển nhiên. Năm thứ 7, Trình Trấn Đông bệnh nặng. Cuộc chiến kế nhiệm thật sự bắt đầu. Cảnh nghiêm có cổ phần và nhóm của đồng cũ. Cảnh thâm có thành tích nhưng thiếu hậu thuẫn. Tôi bắt đầu vận động những mối quan hệ mà mình tích lũy nhiều năm. Tôi thuyết phục cha đưa phần hợp tác của nhánh chúng tôi về phía Cảnh thâm. Tôi thật chỉ chủ động nhường cho Minh Hạ một vị trí trong Tống gia để đổi lấy việc bác cả không can thiệp và lựa chọn của tôi. Minh Hạ hỏi, em làm tất cả chỉ vì một người đàn ông. Tôi đáp, không. Em làm vì thứ em đã đầu tư 7 năm. Chị nhìn tôi rồi nói, Nhược Vi, em đang nói về người yêu hay một dự án. Tôi không thích câu hỏi đó. Tôi bỏ đi. Nhưng tôi ấy nằm cảnh điện thoại chờ Cảnh thâm gọi. Tôi đã nghĩ rất lâu. Tôi yêu anh. Tôi chắc chắn. Chỉ là tình yêu của chúng tôi đã gắn với quyền lực quá lâu đến mức chính tôi cũng không còn biết đâu là danh giới. Năm thứ 8, Cảnh thâm gần như đã ngang Cảnh Nghiêm. Đó cũng là lúc Hứa Thanh Du xuất hiện. Thanh Du là con gái của người sáng lập một quỹ đầu tư đang nắm lượng của phân đủ để ảnh hưởng của bỏ phiếu cuối cùng. Cô ấy không giống những người phụ nữ tôi từng đề phòng. Thanh Du thương minh, điềm tĩnh, không hề cố quyến rũ Cảnh thâm. Chính vì vậy tôi cảm thấy không thể coi thường. Lần đầu gặp cô ấy, tôi đã biết một ngày nào đó cô ấy sẽ trở thành vấn đề. Tôi hỏi Cảnh thâm quan hệ giữa họ là gì. Anh nói công việc. Tôi tin, sau đó Trình Trấn Đông để nghĩ một cuộc hôn nhân giữa Cảnh thâm và Thanh Du. Cảnh thâm từ chối. Tôi biết chuyện không phải từ anh mà từ người khác. Tôi ấy tôi hỏi, sao không nói với em. Anh nói vì đã từ chối rồi, không cần khiến tôi suy nghĩ. Tôi hỏi, anh từ chối được bao lâu. Anh nhìn tôi, em không tin anh. Tôi đáp, em không tin chiếc ghế anh đã mất 8 năm để giành. Anh dẫn, tôi cũng dẫn. Nhưng cuối cùng anh ôm tôi rất lâu rồi nói, Nhược Vi, đợi anh thêm một chút. Tôi hỏi, bao lâu. Đến cuộc họp của Đông năm sau. Rồi sau, anh đáp, anh sẽ không để em phải đứng phía sau nữa. Tôi lại tin, năm thứ 9, chính chấn đồng qua đời. Cảnh nghiêm và Cảnh thâm chính thức đối đầu. Quý của hứa ra trở thành lá phiếu quyết định. Cảnh thâm bắt đầu gặp Thanh Du nhiều hơn. Tôi không hỏi. Tôi tiếp tục làm những việc mình rõ nhất. Tôi phát hiện một nhóm của Đông nhỏ đang muốn bán lại cổ phần, âm thầm kết nối họ với những người thân Cảnh thâm. Tôi tìm được một sai sót trong thương vụ cũ của Cảnh nghiêm đủ để khiến hội đồng nghi ngờ năng lực quan trị. Tôi thuy phục một người từng ghét Cảnh thâm bỏ phiếu Trung lập. Tôi làm tất cả trong khi Cảnh thâm ngày càng ít thời gian gặp tôi. Có hông anh hẹn ăn tối rồi không đến? Tôi ngồi trong nhà hàng gần 2 tiếng. Gần 11 giờ anh mới gọi, xin lỗi, anh đang ở cùng Thanh Du và nhóm quỹ. Tôi nói không sao. Anh im lặng rồi hỏi, em dẫn à. Tôi nhìn chiếc bánh đã được nhân viên mang ra rồi lại mang vào vì để quá lâu. Không. Tôi lại nói câu mình đã học từ nhỏ. Tôi không sao. Tôi không cần. Tôi không dẫn. Chỉ có điều lần đầu tiên trong 10 năm, người đàn ông hiểu tôi nhất lại tin câu ấy. Năm thứ 10, Cảnh thâm thắng. Cuộc bỏ phiếu kết thúc lúc 4 giờ chiều. Anh trở thành chủ tịch mới của Trình thị với với tỷ lệ rất nhỏ. Khi kết quả được công bố, tôi ngồi một mình trong xe dưới tầng hầm. Cảnh thâm gọi cho tôi. Dọc anh khán đi Nhược Vi. Tôi cười, chúc mừng anh. Anh im vài giây rồi nói, không có em, anh không đến được hôm nay. Tôi hỏi, anh có nhớ mình từng hứa gì không? Anh không trả lời ngay. Chỉ vài giây ấy thôi. Tôi đã biết. Nhưng tôi vẫn cho anh cơ hội. Tôi nói, tối nay em chờ anh. Cảnh thâm bảo, được. 3 ngày sau Trình thị." 

# ==========================================
# CÁC HÀM XỬ LÝ EDGE-TTS
# ==========================================
async def _generate_edge_audio_async(text: str, output_path: str, voice: str):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(output_path)
            return True
        except Exception as e:
            print(f"[Edge-TTS] Lỗi (lần {attempt+1}): {e}")
            if attempt == max_retries - 1:
                raise e
            await asyncio.sleep(2)

def _split_text(text: str, max_length: int = 1500) -> list:
    sentences = re.split(r'(?<=[.!?]) +', text)
    chunks = []
    current_chunk = ""
    for sentence in sentences:
        if len(sentence) > max_length:
            if current_chunk: chunks.append(current_chunk.strip()); current_chunk = ""
            for i in range(0, len(sentence), max_length):
                chunks.append(sentence[i:i+max_length].strip())
        else:
            if len(current_chunk) + len(sentence) < max_length:
                current_chunk += sentence + " "
            else:
                if current_chunk: chunks.append(current_chunk.strip())
                current_chunk = sentence + " "
    if current_chunk: chunks.append(current_chunk.strip())
    return chunks

def _process_edge_tts(text: str, output_dir: str, voice: str) -> str:
    final_output_path = os.path.join(output_dir, "voiceover.mp3")
    chunks = _split_text(text, max_length=1500)
    
    print(f"[Edge-TTS] Xử lý {len(chunks)} phần...")
    
    if len(chunks) == 1:
        asyncio.run(_generate_edge_audio_async(text, final_output_path, voice))
    else:
        temp_files = []
        try:
            for i, chunk in enumerate(chunks):
                temp_path = os.path.join(output_dir, f"temp_{i}.mp3")
                asyncio.run(_generate_edge_audio_async(chunk, temp_path, voice))
                temp_files.append(temp_path)
            
            with open("config.yaml", "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
            ffmpeg_exe = os.path.join(cfg["ffmpeg"]["path"], "ffmpeg.exe")
            
            list_file = os.path.join(output_dir, "temp_list.txt")
            with open(list_file, "w", encoding="utf-8") as f:
                for tf in temp_files:
                    f.write(f"file '{tf.replace(chr(92), '/')}'\n")
            
            cmd = [ffmpeg_exe, "-y", "-f", "concat", "-safe", "0", "-i", list_file, "-c", "copy", final_output_path]
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            for tf in temp_files:
                if os.path.exists(tf): os.remove(tf)
            if os.path.exists(list_file): os.remove(list_file)
        except Exception as e:
            print(f"[Edge-TTS] Lỗi ghép file: {e}")
            return None
            
    return final_output_path

# ==========================================
# CÁC HÀM XỬ LÝ KORVA-TTS
# ==========================================
def _get_korva_tts():
    global _korva_tts
    if _korva_tts is None and HAS_KORVA:
        print("[KorvaTTS] Đang khởi tạo model...")
        _korva_tts = KorvaTTS()
    return _korva_tts

def _process_korva_tts(text: str, output_dir: str, voice: str) -> str:
    final_output_path = os.path.join(output_dir, "voiceover.wav")
    if not HAS_KORVA:
        raise Exception("Chưa cài đặt thư viện korvatts.")
    
    tts = _get_korva_tts()
    wav, dur = tts.synthesize(text, voice=voice, lang="vi", total_steps=32, speed=1.0)
    tts.save_audio(wav, final_output_path)
    return final_output_path

# ==========================================
# CÁC HÀM XỬ LÝ VIENEU-TTS (CLONE GIỌNG)
# ==========================================
def _get_vieneu():
    global _vieneu_tts
    if _vieneu_tts is None and HAS_VIENEU:
        print("[VieNeu-TTS] Đang khởi tạo model (lần đầu sẽ tải model)...")
        _vieneu_tts = Vieneu()
    return _vieneu_tts

def _process_vieneu_clone(text: str, output_dir: str) -> str:
    final_output_path = os.path.join(output_dir, "voiceover.wav")
    if not HAS_VIENEU:
        raise Exception("Chưa cài đặt thư viện vieneu.")
    
    if not os.path.exists(REF_AUDIO_PATH):
        raise Exception(f"Không tìm thấy file giọng mẫu: {REF_AUDIO_PATH}")
        
    tts = _get_vieneu()
    print(f"[VieNeu-TTS] Đang tạo giọng clone từ: {REF_AUDIO_PATH}...")
    
    # CHIA NHỎ VĂN BẢN để tránh tràn RAM
    chunks = _split_text(text, max_length=200)
    temp_files = []
    
    try:
        for i, chunk in enumerate(chunks):
            print(f"  -> Đang xử lý đoạn {i+1}/{len(chunks)}...")
            temp_path = os.path.join(output_dir, f"temp_vieneu_{i}.wav")
            
            audio = tts.infer(
                text=chunk,
                ref_audio=REF_AUDIO_PATH,
                ref_text=REF_TEXT
            )
            tts.save(audio, temp_path)
            temp_files.append(temp_path)
            
        # Ghép các file âm thanh nhỏ lại bằng FFmpeg
        print("[VieNeu-TTS] Đang ghép các đoạn âm thanh...")
        with open("config.yaml", "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        ffmpeg_exe = os.path.join(cfg["ffmpeg"]["path"], "ffmpeg.exe")
        
        list_file = os.path.join(output_dir, "temp_list_vieneu.txt")
        
        # SỬ DỤNG ĐƯỜNG DẪN TUYỆT ĐỐI CHO CÁC FILE WAV
        with open(list_file, "w", encoding="utf-8") as f:
            for tf in temp_files:
                abs_tf = os.path.abspath(tf).replace("\\", "/")
                f.write(f"file '{abs_tf}'\n")
                
        abs_output_path = os.path.abspath(final_output_path).replace("\\", "/")
        abs_list_file = os.path.abspath(list_file).replace("\\", "/")
        
        # Ép FFmpeg render lại âm thanh để tránh lỗi codec
        cmd = [
            ffmpeg_exe, "-y", 
            "-f", "concat", "-safe", "0", "-i", abs_list_file, 
            "-c:a", "pcm_s16le", 
            abs_output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print("LỖI FFMPEG CHI TIẾT:", result.stderr)
            raise Exception("Lỗi FFmpeg khi ghép âm thanh.")
        
        # Dọn dẹp file tạm
        for tf in temp_files:
            if os.path.exists(tf): os.remove(tf)
        if os.path.exists(list_file): os.remove(list_file)
        
        return final_output_path
        
    except Exception as e:
        print(f"[VieNeu-TTS] Lỗi: {e}")
        for tf in temp_files:
            if os.path.exists(tf): os.remove(tf)
        if os.path.exists(list_file): os.remove(list_file)
        raise e

# ==========================================
# HÀM CHÍNH ĐIỀU PHỐI
# ==========================================
def text_to_speech(text: str, output_dir: str, voice: str = "vi-VN-HoaiMyNeural") -> tuple:
    os.makedirs(output_dir, exist_ok=True)
    print(f"[TTS] Bắt đầu tạo âm thanh. Giọng: {voice}")
    
    try:
        if voice == "clone_ngoc_huyen":
            final_path = _process_vieneu_clone(text, output_dir)
        elif voice == "ngoc_huyen":
            final_path = _process_korva_tts(text, output_dir, voice)
        else:
            final_path = _process_edge_tts(text, output_dir, voice)
            
        if not final_path or not os.path.exists(final_path):
            return None, 0.0

        with open("config.yaml", "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        ffprobe_path = os.path.join(cfg["ffmpeg"]["path"], "ffprobe.exe")
        
        duration = get_video_duration(final_path, ffprobe_path)
        print(f"[TTS] Đã tạo xong. Thời lượng: {duration:.1f} giây")
        return final_path, duration
        
    except Exception as e:
        print(f"[TTS] Lỗi tạo giọng đọc: {e}")
        return None, 0.0