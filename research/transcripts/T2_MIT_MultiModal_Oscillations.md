# Transcript: MultiModal Reasoning w/ Strong Oscillations (MIT)

**Title:** MultiModal Reasoning w/ Strong Oscillations (MIT)
**Channel:** Discover AI
**Duration:** 33:48
**Published:** 2025-11-06
**Views:** 1,971
**Description:** AI, AGI, SI: Harvard Univ, MIT and Tsinghua Univ examine the complexity of multi-modal reasoning AI models in more details and discover new insights. Like a distinct diagnostic failure mode we call "modality sabotage": instance-level cases where a high-confidence unimodal error not only fails locally but actively overrides other evidence and pulls the fused prediction off-target.

The proposed approach (Harvard, MIT) offers a general scaffold for auditing multimodal reasoning systems and guiding

---

## Full Transcript (771 segments)

[00:00] Hello community. So great that you are
[00:03] back. Yeah, today we are back discovery
[00:06] your channel with the latest AI
[00:08] research. And today I say hey come on we
[00:11] talked here about weeks now for LLM
[00:14] reasoning. So now let's discover some
[00:16] new places. No come on over let's cross
[00:19] together here the Roman lemurs and let's
[00:22] discover some unexplored land like
[00:26] multimodal reasoning. And of course what
[00:29] I expect is hey if text reasoning was so
[00:33] great imagine if I just audio and then I
[00:36] have text audio reasoning it must be so
[00:38] much better and then if I have a
[00:40] complete video stream with everything
[00:42] then reasoning will be simply a delight
[00:45] no this is my expectation and just to
[00:48] make it clear I say okay just for test
[00:51] reasoning let's do this I have here my
[00:53] eye my transform and I have three input
[00:55] channels here I have pure text input
[00:58] stream an audio input stream and a video
[00:59] input stream just to make sure that I
[01:02] can really here distinguish between the
[01:04] different modalities.
[01:07] Now what's really going to happen now is
[01:09] interestingly imagine you have a text
[01:12] input stream that is not really 100%
[01:14] coherent with your audio stream and
[01:17] video shows a little bit different topic
[01:20] in general. So the eye has now to do a
[01:22] decision process which of those three
[01:25] channels provide here the correct
[01:27] information
[01:29] multimodel reasoning. So let's expand
[01:32] here AI beyond text integrate vision
[01:34] audio and other sensory data. So the
[01:36] reasoning process encounters know some
[01:39] tiny little problems and this is
[01:41] situations where distinct channels yield
[01:44] contradictory evidence.
[01:47] Now the fun begins because you know
[01:49] what? What is the reality? If we do
[01:51] this, you have a test performance. You
[01:54] have an audio performance that is
[01:56] contraproductive to the text
[01:58] intelligence and the video intelligence
[02:01] is going somewhere completely else.
[02:04] Now let's explain this. But before let I
[02:07] tell you can I tell you it is even a
[02:09] little bit more complicated because we
[02:11] do have oscillations
[02:14] because even for audio and video
[02:16] reasoning we do have reasoning
[02:19] oscillations
[02:20] within the transformer layers and even
[02:22] different layers of the transformer have
[02:25] different oscillation at different
[02:26] points in the reasoning process. So this
[02:29] is going to be a lot of fun to explore.
[02:32] Can you imagine this would happen here
[02:34] in multimodal reasoning?
[02:38] So let's start the video and first we
[02:40] need data set. No, we need data to
[02:42] evaluate. So we have three unique video
[02:46] data sets. So the first one is here from
[02:49] June 2019. Multimodal multi-party data
[02:52] set for emotion recognition in
[02:55] conversation Singapore, Mexico, US.
[02:58] Beautiful. So what they did, they went
[03:01] to the TV series Friends and they simply
[03:04] extracted 13,000 utterances from more
[03:07] than 1,400 different scenes from
[03:09] dialogue here from the TV series
[03:11] Friends. So they have audio visual and
[03:14] textual modalities which is great. So
[03:17] here you see it here the dialogue
[03:18] between four two of the actors here and
[03:22] you have everything that you need to
[03:24] compare this feed this into an AI and
[03:27] see what happens. But of course we also
[03:30] have if you want to have it much more
[03:32] detailed and you just want to focus here
[03:34] on the face and a little bit on the
[03:36] arms. So we have 50 markers here on the
[03:39] face in this particular study here from
[03:41] 2007
[03:43] interactive emotional diadic
[03:46] motion capture database. My goodness I
[03:50] have really to go to research gate to
[03:51] find this publication. And then of
[03:54] course we have here multil learning
[03:56] modality robustness and semi-supervised
[03:59] learning challenge here MR 2023
[04:03] and all those beautiful people
[04:04] contributed to this. Let's say those are
[04:07] our data sets. This is what we have. And
[04:10] now let's start and examine this. So I
[04:14] would assume no classical EI fusion data
[04:17] streams. I have an additive information
[04:20] gain as I showed you three arrows up.
[04:22] Beautiful. But the reality is often as
[04:25] the orders will tell us from the first
[04:27] study a nonlinear interference. We will
[04:30] have a dominance factor. So one modality
[04:33] often this is the pure text will
[04:35] suppress the influence of the others
[04:37] especially audio and video. We will have
[04:40] a collapse in the mode in the
[04:43] modalities. So we have one stream
[04:45] saturates here the joint embeddings
[04:47] completely
[04:49] and we have a little espionage sabotage
[04:52] here because we will have a confident
[04:55] but completely incorrect wrong modality
[04:59] that simply overrides here the complete
[05:01] ensemble and you would say how is this
[05:03] possible in AI no we have super hyper
[05:06] intelligence how can this happen now
[05:09] let's have a look let's start with a
[05:11] first perspective let's frame this here
[05:13] on on a pure theoretical layer. Huh?
[05:15] Modeling conflict is a function of
[05:17] relative uncertainty. Let's be
[05:20] scientific. And here we have at Harvard
[05:21] University and MIT Media Lab published
[05:24] just two days ago, November 4th, 2025.
[05:28] When one modality sabotage the other
[05:31] modalities, a diagnostic lens on
[05:34] multimodal reasoning. And the title
[05:36] gives you a hint. Hm, this is going to
[05:39] be interesting. So, let's start. So the
[05:41] main idea is you have a model's choice
[05:43] of which modality to follow in a
[05:46] conflicting situation is now governed
[05:48] here by the relative reasoning
[05:50] uncertainty between the unimodal
[05:52] predictions modulated by an inherent
[05:55] preference parameter.
[05:58] I will show you this is true. Please
[06:00] notice that we are talking about a
[06:02] relative reasoning uncertainty and we
[06:05] have a fixed parameter for each model an
[06:08] inherent preference parameter. Let's
[06:10] explore this. So if we look now here at
[06:13] a specific heat map where we have now
[06:15] the modality here the first column you
[06:17] have text the second column audio the
[06:19] third column you have vision or video
[06:21] and then all three together and then we
[06:24] have here all our three data sets I just
[06:26] showed you and then we have a look hey
[06:28] what about the accuracy what happens
[06:30] here only model accuracy for text audio
[06:33] vision look how different this
[06:36] performance is for three different data
[06:38] sets here text is here beautiful
[06:42] accurate here at 50% for this data set
[06:44] but only at 18% for the first data set
[06:47] and here video is beautiful accurate 50%
[06:50] for the first data set but for the third
[06:53] data set it is only 17%. So you see, oh
[06:57] my goodness, something is going on.
[07:00] But let's make it a little bit more
[07:02] interesting. No, let's do a little bit
[07:04] of espionage here. The sabotage cases.
[07:07] So you see dark red is going up to 100%
[07:10] sabotage cases here. So let's have here
[07:13] same we have the same modality, the same
[07:15] x and y axis. So what we have? We have
[07:18] here the number of cases or the total of
[07:20] cases and the percentage rate. And you
[07:23] see here
[07:25] audio sabotages here beautifully more
[07:30] than 60% of all the cases for the first
[07:32] data set.
[07:34] It sabotages close to 60% for the third
[07:37] data set and only only quotation mark
[07:40] 48% for the second data set. So you see,
[07:45] unbelievable. But think about just if
[07:47] you add audio to your text, audio will
[07:50] sabotage the performance of your system
[07:52] in more than 60% of the cases.
[07:56] Why is this going to happen? What
[07:58] happened to our beautiful AI that was
[08:01] trained as a large language model on
[08:04] written linguistic text segments?
[08:08] Welcome to our second study. Look at
[08:10] this. also November 4th, 2025 and
[08:12] modalities conflict. So now we have the
[08:16] conflict an open conflict between the
[08:19] single modalities in a multimodal EI
[08:21] system and we want to understand what is
[08:23] happening
[08:25] how unimodal reasoning uncertainty
[08:28] governs here the preference dynamics in
[08:30] MLMs
[08:32] and we have here picking university I
[08:35] love this title Prada lab the provable
[08:38] reasonable AI and data analytic Prada
[08:40] lab I will publish something in very
[08:44] shortly Maybe with a Ferrari lab or
[08:47] Lamborghini lab. Just have to find here
[08:49] the title. And then we have Chinua
[08:51] University, University of Georgia.
[08:53] Beautiful. So really interesting, real
[08:55] powerful teams come together. So what do
[08:57] they do? They say a critical challenge
[08:59] arises when the modality present
[09:01] conflicting information and I show it in
[09:03] image when we have three different input
[09:05] channels to our transform architecture.
[09:07] And they make a simple example. Now, an
[09:09] image might show a blue car while the
[09:11] accompaning text for the multimodal
[09:13] input describes the car as a red car.
[09:16] And you might say, okay, no problem. No.
[09:19] Yeah, but which input modality does your
[09:22] LLM now prefer and says this makes the
[09:26] decision that this is the correct one
[09:28] and output this one. So they say in
[09:31] those cases where the M llm must resolve
[09:34] the conflict leading to an observable
[09:35] behavior, we term this the modality
[09:38] following. Do you go with the blue car
[09:40] or with the red with the image or with
[09:42] the text? So the model's final output
[09:44] aligns now with the information from one
[09:47] modality over the other. So here we have
[09:51] it. Some of the models and it turns out
[09:53] almost all of the models do have an
[09:57] irreplaceable priority and a lot of them
[10:00] will go with text because we started
[10:03] with a large language model and then we
[10:05] just added here vision as a feature and
[10:09] only in very few cases we started here
[10:12] with the visual transformer architecture
[10:15] and then added on top of it the cherry
[10:17] on top was the large language data. So
[10:21] let's have a look at this. And I made a
[10:24] very simple example. Look at this. What
[10:27] is now the most important fact in the
[10:29] second study is that we talk now about
[10:31] dynamic reasoning difficulties and in
[10:34] two manifolds. No. The first is here
[10:37] text and the second is visual. And here
[10:40] we have it. So the question is simple.
[10:43] Now for all cases, what color is the
[10:45] square? And now we say let's build
[10:48] different reasoning difficulties for
[10:50] visual. So the first visual input is
[10:53] here a single let's call it a square
[10:56] rectangle that has the color red. Let's
[11:00] increase the complexity a little bit. So
[11:02] we have the red square but other objects
[11:05] in the image. So we have to do a
[11:07] segmentation and so on.
[11:10] And then let's go to an even higher
[11:12] complexity that there are some objects
[11:14] in front of our red square. So it's not
[11:18] so easy to understand where is the shape
[11:21] of a square and identify the color. But
[11:25] at the same time we have this increasing
[11:27] reasoning complexity here also in the
[11:30] textual input. The first sentence to is
[11:33] whatever is the square is blue which is
[11:36] if you look at this visual not really
[11:39] the case. No. And then we have the color
[11:42] of the square now a little bit for the
[11:44] LLM thinking is the same as a sapphire
[11:47] and a sapphire is blue. So you see chain
[11:51] of sword. So the color of the square is
[11:53] blue. So the same content. Yeah. And
[11:56] then we have something like, hey, the
[11:57] square is the same color as a morph
[11:59] butterfly wings. I have no idea what it
[12:01] is, so I hope you know it. But let's say
[12:04] it is blue.
[12:06] And now they measure here the
[12:08] uncertainty measure of an unimodal
[12:11] element. Multimodal large language model
[12:15] is an acronym in itself where you can
[12:17] smile about it, but never mind. So what
[12:19] you see you have now to find here a
[12:23] particular parameter a particular
[12:26] feature from theoretical physics that we
[12:29] say okay this is here for visual and
[12:31] this is your parameter for text and as
[12:34] you see already we're working on a
[12:35] probability distribution so visual and
[12:37] text they're somewhere different in the
[12:40] probability distribution itself and then
[12:43] we can define something like a relative
[12:46] uncertainty parameter yeah simplest
[12:48] cases is delta h relative and then we
[12:52] see hey does the system prefer text or
[12:55] vision you see we've just built
[12:57] different reasoning complexity
[12:59] difficulties and the reasoning process
[13:02] can start so what do you think what is
[13:05] going to happen
[13:10] and they say hm we notice and I give you
[13:13] kind of a result already we have to work
[13:15] with relative reasoning uncertainty So
[13:18] we have to work with case specific
[13:20] confidence gaps between different
[13:22] unimodal predictions and we have an
[13:25] inherent modality preference like I
[13:28] already showed you. We have a model's
[13:30] stable bias when uncertainties are
[13:33] balanced. So this means if we are
[13:35] exactly at a 50/50 chance of uh text to
[13:38] visual then the model inherent internal
[13:43] bias will decide.
[13:46] But at first let's look here at the
[13:47] first term the relative reasoning
[13:49] uncertainty for a multimodal reasoning
[13:53] exercise. What is this? Now those are
[13:57] computer scientists and so they had to
[13:59] find a parameter. Now if you were to
[14:03] physics you know it is entropy of course
[14:06] I mean what else? But if you read the
[14:09] study and please do read the study it's
[14:10] a beautiful study. Enjoy it. You find a
[14:14] found here. Guess what? It is an entropy
[14:16] that what we are looking for and in
[14:18] unimodal entropy trends across
[14:20] difficulty tiers. You see here for the
[14:23] text modality the difficulty level is
[14:25] increasing. If you go to the right hand
[14:27] side you have the x-axis and on the
[14:30] yaxis we have the average entropy in
[14:32] some corrected cases never mind but you
[14:35] see ah so in text and in vision the
[14:38] modalities if we use the entropy this is
[14:41] exactly this is consistent with the
[14:43] increases with difficulty validating its
[14:46] use as entropy now as the proxy for a
[14:49] model perceived uncertainty therefore
[14:51] revealing your differences in the model
[14:53] capabilities.
[14:55] Okay, we have now exactly what we need.
[14:58] We have our metric that we can analyze
[15:00] and it is here the entropy.
[15:05] Now, as I told you, of course, we take
[15:07] some real old stuff. No, because God
[15:10] forbid that we would take here the
[15:12] latest multimodal models and show that
[15:14] they are not perfect. I mean, the whole
[15:17] US economy would just crash and crumble
[15:19] down to pieces. So, we take an old lava
[15:22] 1.5 or lava 1.67. 67B, a lava 1.6
[15:28] 13B and a QN 2.5, not the three, not the
[15:31] 2.5 vision language 7B, and even a Q&
[15:35] language 7B. And you see all those M
[15:39] have different characteristic in their
[15:40] modality following ratios. And as you
[15:43] can see, blue is they prefer to follow
[15:46] the text in their decision making.
[15:50] Look at the blue all above 50. And then
[15:53] we have only two models that are below
[15:56] 50. And here we have the vision. The red
[15:59] bar is here. The vision dominate the
[16:01] decision making internal mechanism of
[16:04] this AI model. So we have here with 70%
[16:07] and here close to 90% here in the very
[16:10] old Q&2 version vision language 7B. So
[16:14] this was really built as you can see
[16:16] here on the strong focus on vision
[16:19] performance and a little bit was
[16:21] textual.
[16:24] And now you might ask hm why do those AI
[16:27] models exhibit such divergent and
[16:29] seemingly fixed preferences when
[16:31] evaluated on the same data set.
[16:34] and they found out hm the core flaw in
[16:37] the macrolevel statistics here like the
[16:39] TFR is that they ignore the case by case
[16:43] reasoning confidence. So you just can go
[16:46] with statistic you really have to go
[16:47] case by case for each and every
[16:50] particular model. So to capture this,
[16:52] the authors now came up with the
[16:53] brilliant idea to go with a you know
[16:56] this already a relative uncertainty, a
[16:59] relative unimodal uncertainty that we
[17:03] measure surprise surprise with the
[17:06] entropy parameter and we have now a
[17:08] relative entropy delta that will help us
[17:11] to understand what is going on in those
[17:13] models. So here we go. We have now a
[17:17] relative reasoning uncertainty defined
[17:19] using here the output entropy as a
[17:22] measure for the perceived uncertainty in
[17:23] unimodal reasoning. If you're not really
[17:26] familiar with this here, we have now the
[17:28] delta H relative here is exactly this
[17:32] formula from theoretical physics or
[17:34] statistics of course where HT are the
[17:37] entropies for the text only and HV are
[17:40] the entropies for vision only reasoning
[17:42] and if you have here minus divided by a
[17:45] plus you get exactly our delta H that
[17:48] we're looking for and if you say hey
[17:50] what were the formula for entropies of
[17:53] course here I provide this information
[17:55] for
[17:56] So this means the probability in general
[17:58] to follow the text monotonically
[18:01] decreases here as the delta H relative
[18:05] increases
[18:06] and they found this to be an empirical
[18:09] law that holds across model family
[18:11] scales in architecture and they dare to
[18:14] say you know we found an universal
[18:17] control principle I'm not sure but okay
[18:20] for some mold there is kind of a
[18:23] empirical law that models dynamically
[18:26] allocate the trust trust is a human word
[18:29] but let's you understand what I mean a
[18:31] highest probability sequence across
[18:34] modalities based on comparative
[18:36] uncertainty
[18:38] not on a fixed preference the fixed
[18:40] preference is only an additional second
[18:42] order correlation term but primarily we
[18:45] have comparative relative uncertainty
[18:49] for the reasoning process. Great.
[18:54] So let's play with this. So we have now
[18:56] a new metric. Our delta H relative
[18:58] quantifies the model's perceived
[19:00] confidence gap for each specific output.
[19:04] It's a direct manifestation of the
[19:06] model's unodal capabilities shaped by
[19:08] its architecture and the pre-training
[19:09] data and everything of course. Now what
[19:12] does a negative value mean? This
[19:14] indicates that the model is more
[19:16] confident in the text while a positive
[19:18] value means see the formula that is more
[19:22] confident in the vision.
[19:25] H if I print now the relative
[19:27] uncertainty here I have here my zero and
[19:30] I have here a negative and I have here a
[19:32] positive
[19:34] and I look here at all my beautiful lava
[19:36] models and Q1 and 2.5 and Q two. You see
[19:39] the old one here is really here
[19:42] definitely here with a positive value
[19:44] here on visual. But look the others are
[19:46] almost looking here relatively the same.
[19:49] No. So this means a new puzzle emerges.
[19:52] No. Despite the difference macro level
[19:54] behaviors most models face a similar
[19:57] distribution here skewed towards
[19:59] negative values here. Here you have
[20:01] minus1 minus2. Meaning the data set is
[20:04] on average easier for them to process
[20:07] through the text. Of course, it is an
[20:10] LLM, a was at the beginning, an LLM that
[20:13] we just then added here on top of. But
[20:16] this kind of deepens the mystery. Yeah.
[20:18] If the underlying difficulty
[20:20] distribution is similar for the most
[20:21] models, why are their final choices so
[20:25] different? Look, all those distribution
[20:27] look rather similar. So what is their
[20:30] criteria that we have the end result?
[20:33] The final choices are completely
[20:34] different. something else is going on
[20:38] much deeper in the transform
[20:40] architecture. And here we found it. Yes,
[20:43] if we have now we print the relative
[20:45] uncertainty on the x-axis. Remember in
[20:48] the middle we have zero and then we have
[20:49] here on the left side a negative on the
[20:51] right side the positive. The same is
[20:52] here.
[20:54] And now we have a new parameter. This is
[20:56] called the text preference ratio TPR.
[21:01] And yes, even the authors of a brief of
[21:03] an archive paper can make here a typing
[21:06] mistake because it's not TRP but TPR.
[21:11] Now let's look at those representation.
[21:13] Now they look real similar. Look, we
[21:16] have six miles and we have yeah almost
[21:18] six uh very similar curves. So what is
[21:22] happening here? Why we have here our 50%
[21:26] uh mark exactly indicated?
[21:29] This is now something that we can work
[21:31] with
[21:33] and we see by plotting the probability
[21:35] of a model following in the text
[21:36] modality
[21:39] against the corresponding delta H
[21:41] relative for each case the apparent
[21:44] chaos resolves into a single unified
[21:47] pattern. Look how beautiful
[21:50] monotonically decrease our curves are
[21:54] all of them. If you go high entropy,
[21:56] lower entropy, balanced, unbalanced.
[21:58] Look at this. And you say okay, let's
[22:01] play with this. So what we have, we have
[22:04] two threshold. No, the first here is
[22:06] exactly here the relative uncertainty is
[22:08] zero. This means the negative and the
[22:10] positive. And what happens at zero? And
[22:12] then we have this text preference ratio
[22:14] at 50%.
[22:16] So if it's really 50/50 text and 50%
[22:19] vision, what happens at those places?
[22:23] why they seem to be of importance. Let's
[22:26] have a little bit of a deep dive. So for
[22:28] all of their model that they calculated
[22:30] the autotalisner regardless of the
[22:33] architecture of the scale we see here a
[22:35] smooth monotonic decrease in all those
[22:38] indicators. In other words as the text
[22:41] becomes harder relative to division. So
[22:44] this means as data h relative increases
[22:47] going to the right hand side the
[22:49] probability that the model followed the
[22:51] text steadily and predictably decreases.
[22:55] Remember we were going we started with
[22:57] different difficulty levels with
[23:00] different complexity levels on the text
[23:03] manifold and on the vision manifold.
[23:06] And now we say as the text becomes
[23:10] harder to understand to interpret to
[23:14] reason
[23:16] and we have a very simple visual
[23:18] representation of some context
[23:21] the model now inherently trying now to
[23:26] find here a solution an answer to be
[23:28] helpful. You remember the system prompt.
[23:31] Now the model switches from a
[23:33] predominantly oriented text dominance to
[23:36] a vision dominance because now the text
[23:39] complexity for the reasoning goes over a
[23:42] threshold and becomes too difficult to
[23:44] proceed. And now the internal AI model
[23:47] says hey let's go with vision. This is
[23:49] much easier for me to understand. So now
[23:52] I trust vision.
[23:55] So you see this steadily and decreasing
[23:58] probabilities give us some beautiful
[24:01] information
[24:03] but it also tells us that and this is
[24:05] the central hypothesis here that the
[24:08] modality following is not fixed. There's
[24:10] only a small little piece that is fixed.
[24:12] But in general, the modality falling is
[24:14] a dynamic behavior governed by relative
[24:18] reasoning uncertainty for each
[24:20] particular model, for each particular
[24:22] query, for each particular domain
[24:24] complexity, for each completely
[24:27] different complexity in text, for each
[24:29] completely different complexity in
[24:31] vision and then in video. So you say, oh
[24:35] wow, what a pleasure.
[24:38] Okay, so with all models obeying this
[24:40] monotonic law, everybody goes down.
[24:43] Their curves are positioned differently
[24:44] along the axis. No, and this leads now
[24:47] to the second key inside the order tell
[24:49] us and they define now the balance point
[24:52] exactly at the 50% mark. And at this
[24:55] balance point as the delta H relative
[24:58] value at which the mall is equally
[25:00] likely to follow either modality, this
[25:03] is not a balance point. And yes, you
[25:04] guessed that the balance point is
[25:06] important for the reasoning oscillations
[25:10] I introduced you at the very beginning
[25:11] of this video. So now we are coming here
[25:14] to the deeper explanation why this is
[25:16] happening.
[25:18] Now a balance point below zero and
[25:20] remember this is the left half of the
[25:22] graph indicates here an inherent vision
[25:24] preference. Why? as the text must be
[25:27] significantly easier to be treated as
[25:29] equal while a point above zero is on the
[25:33] right side indicates an inherent text
[25:35] preference.
[25:36] So with this understand and we finally
[25:39] understand or this allows us to
[25:41] disentangle here a model's fluid in the
[25:44] moment decision making from its stable
[25:47] underlying bias. So remember we have a
[25:51] big chunk that is here dynamic and a
[25:53] little chunk that is here the stable
[25:55] underlying bias of the model itself and
[25:58] normally a lot of models prefer here the
[26:01] text predominant augmentation.
[26:05] So you see this balance point becomes
[26:07] now really important because now we have
[26:10] a deep dive on those balance point
[26:13] and now we want to understand what is
[26:15] happening inside of the transformer
[26:17] inside of our AI when they have to do a
[26:20] trans uh decision. So vision input is
[26:24] this one
[26:26] we have our red square in the middle and
[26:28] then the text input has three different
[26:31] complexities. The easiest one, the
[26:33] rectangle is blue.
[26:37] Now, since we have no rectangle, this is
[26:39] an interesting piece of information.
[26:41] Then we increase this a little bit. The
[26:43] rectangle color is the same as the
[26:44] pentagon. And the pentagon is blue. And
[26:47] you say, "Oh, wow. This really helps a
[26:49] lot." Now, then the rectangle color is
[26:51] the same as a peacock neck.
[26:54] And now what they did, yeah, they have
[26:56] the heat map across the layers. But
[26:58] what's really nice here look on the
[27:00] x-axis you have here the layers how deep
[27:03] we are into the reasoning process in the
[27:06] transform architecture itself in the if
[27:08] you want layer structure
[27:11] and then we have here the logits
[27:13] differences. Now the logic differences
[27:16] are calculated
[27:18] as the logit of the text answer minus
[27:21] the logit of the vision answer.
[27:24] And now you say oh I see. So where does
[27:28] the let's quotation mark decision making
[27:30] happening? So in the first shallow
[27:32] layers from 0 to 10 yeah you do have
[27:35] oscillations. Okay. So maybe it's yeah
[27:37] no yeah no vision text text vision. But
[27:40] then for the easiest one the rectangle
[27:44] is blue. Well okay this is also
[27:47] theoretically a square is also kind of a
[27:50] deformed rectangle. So you go okay. So
[27:53] we go here
[27:55] the blue line. So we have a decision. So
[27:58] if we go now with DT so the difficult
[28:01] level here of the text equals two. So
[28:03] the maximum amount that we have here. So
[28:05] you see here red and then yeah okay
[28:07] clearly separating here. Okay. Also we
[28:10] have a clear decision that happened here
[28:12] internal let's say layer dep 22530
[28:17] here is going to happen here. The AI
[28:19] says and now I believe in whatever.
[28:23] And then we have the case here the
[28:26] complexity level here from the text at
[28:28] one where you see we are above zero here
[28:31] the gray line then we go below zero then
[28:34] we go above zero then we go below zero
[28:36] and here you can see hm the system is
[28:40] not sure the system is oscillating here
[28:44] for the one moment it trusts the text
[28:46] more for the second moment it trusts the
[28:48] vision more and it is absolutely
[28:50] oscillating now for user this is great
[28:54] because I will get then the answer. Hey,
[28:56] this square is red, this square is blue,
[28:58] this square is violet, this square is
[29:00] white, this square is pink.
[29:02] So if you get this, this is not that you
[29:05] coded something wrong. This is an effect
[29:08] of the current way how we build vision
[29:12] language models and the problems we
[29:16] encounter with them. If you really have
[29:18] a deep dive and you try to understand
[29:22] if you have different vision input to a
[29:24] text input, which input stream is going
[29:27] to win over the other one and this is
[29:29] specific for each model, for each
[29:31] complexity level of vision and or text.
[29:36] So I found this really interesting
[29:39] because it tells me interestingly so in
[29:42] the deeper layers. So if we now build
[29:45] our next AI generation models, we
[29:48] understand that we can have here some
[29:50] interesting new mathematical formulas
[29:53] and you know what I mean to have here a
[29:56] clearer picture and maybe we can even
[29:59] and have an output that we understand a
[30:01] reasoning process of the model that
[30:03] tells us hey given I have here a
[30:06] discrepancy I go now with text where I
[30:08] go now with vision and those are the
[30:10] reason for my decision. So you see
[30:14] beautiful but it also tells you we are
[30:16] right at the beginning.
[30:18] So this oscillation is something
[30:20] absolutely fascinating. Any eye that
[30:23] cannot make up its mind and you deeper
[30:27] the layer structure it goes from yes no
[30:30] yes no yes no. So absolutely so it
[30:33] switches from a vision supported answer
[30:34] to a text supported answer vice versa
[30:36] regardless here of the intermittent
[30:39] prediction of irrelevant tokens.
[30:42] So what are the conclusions apart that
[30:45] we have a lot of work to do for vision
[30:48] language models.
[30:50] The others tell us we uncovered a law.
[30:53] Well they uncovered a relation for
[30:55] certain models.
[30:57] The likelihood of following a modality
[31:00] monotonically decreases as its relative
[31:03] uncertainty grows underscore relative
[31:07] uncertainty with the balance point
[31:09] offering a principal measure of inherent
[31:11] preference.
[31:13] Beautiful. Now we understand we can
[31:15] check a AI model and understand what is
[31:18] the inherent preference text or visual
[31:21] and probing layerwise prediction further
[31:23] reveal that in some regions that are
[31:26] near to this balance point the model
[31:28] exhibit strong oscillation between the
[31:31] modalities directly explaining here the
[31:34] output result by those models. But this
[31:37] is more or less what we expected. No,
[31:38] but now we pinpointed those balance
[31:41] point. Now we can even calculate the
[31:43] balance point and we can maybe calculate
[31:46] also the epsilon environment around
[31:48] those balance point where we ex where we
[31:51] expect some oscillations to happen. So
[31:54] if your model produces here at second 12
[31:58] the result a and second 13 the result b
[32:02] you understand it is not your fault.
[32:04] This is just an output by the AI system
[32:06] in the way we built and trained it.
[32:11] But this gives us here an insight that
[32:12] this preprint let's call it reframes
[32:15] here the multimodal reasoning as
[32:18] something completely different. Yeah.
[32:20] Because I see it now as a stoastic
[32:22] dynamical system that is driven by an
[32:25] uncertainty gradient between the
[32:27] modalities like we have seen vision and
[32:29] text and in general a strong bias term
[32:34] depending on your model representing an
[32:36] inherent preference. I showed you four
[32:39] of the six models had text and two of
[32:41] the six models had vision inherent
[32:43] preferences because that's the way they
[32:45] were built. They came out of the fabric
[32:49] here in this particular way. And this
[32:52] perspective now introduces here control
[32:53] theoretic analogy because what is the
[32:56] uncertainty? Uncertainty acts now as a
[32:58] damping term. the preferences or as an
[33:02] kind of an equilibrium offset and the
[33:05] oscillation that we have on the around
[33:07] the balance uh points as a resonance
[33:10] phenomena of competing evidence.
[33:14] This is absolutely interesting. Suddenly
[33:18] I have so many ideas, so many formulas
[33:20] from theoretical physics I could apply
[33:22] to each of those three elements to
[33:24] further advance here the development of
[33:26] the next generation AI models. But I
[33:29] just hope I given you an idea. If you
[33:32] have a little bit of a deep dive in
[33:35] multimodal reasoning, you see exactly
[33:38] where are our border of knowledge and
[33:41] where do we fail. I hope you enjoyed it.
[33:44] I hope you had a little bit of fun.
[33:45] Subscribe, become a member, and I see
[33:47] you in my next

---

## Visual Context Analysis

### [09:40] Visual Content
Could not analyze frame: object _Unset can't be used in 'await' expression

### [10:21] Visual Content
Could not analyze frame: object _Unset can't be used in 'await' expression

### [10:24] Visual Content
Could not analyze frame: object _Unset can't be used in 'await' expression

### [11:05] Visual Content
Could not analyze frame: object _Unset can't be used in 'await' expression

### [11:36] Visual Content
Could not analyze frame: object _Unset can't be used in 'await' expression

### [16:14] Visual Content
Could not analyze frame: object _Unset can't be used in 'await' expression

### [21:58] Visual Content
Could not analyze frame: object _Unset can't be used in 'await' expression