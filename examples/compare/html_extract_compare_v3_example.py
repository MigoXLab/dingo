"""
HTML 提取工具对比评估 V3 示例

这个示例展示了如何使用 LLMHtmlExtractCompareV3 来对比两种 HTML 提取工具的效果。

使用方法：
python examples/compare/html_extract_compare_v3_example.py
"""

import os

from dingo.io import Data
from dingo.model.llm.compare.llm_html_extract_compare_v3 import LLMHtmlExtractCompareV3

OPENAI_MODEL = os.getenv("OPENAI_MODEL")
OPENAI_URL = os.getenv("OPENAI_BASE_URL")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

# 初始化模型
evaluator = LLMHtmlExtractCompareV3()
evaluator.dynamic_config.model = OPENAI_MODEL
evaluator.dynamic_config.key = OPENAI_KEY
evaluator.dynamic_config.api_url = OPENAI_URL

# 示例数据 - 中文网页
example_data_cn = Data(
    data_id="example_cn_001",  # 必需字段
    prompt="""# 机器学习简介

机器学习是人工智能的一个分支，它使计算机能够从数据中学习并做出决策。

## 主要类型

1. 监督学习
2. 无监督学习
3. 强化学习

机器学习在图像识别、自然语言处理等领域有广泛应用。

---
相关文章：
- 深度学习入门
- 神经网络基础
作者：张三
""",
    content="""# 机器学习简介

    机器学习是人工智能的一个分支，它使计算机能够从数据中学习并做出决策。

    ## 主要类型

    1. 监督学习
    2. 无监督学习
    3. 强化学习

    ## 应用场景

    机器学习在图像识别、自然语言处理、推荐系统等领域有广泛应用。

    ## 常用算法

    - 决策树
    - 支持向量机
    - 神经网络

    参考文献：
    [1] Mitchell, T. 1997. Machine Learning.
    """,
    raw_data={
        "language": "zh",  # 指定语言为中文
    }
)

# 示例数据 - 英文网页
example_data_en = Data(
    data_id="example_en_001",  # 必需字段
    prompt=r"""In previous lectures, we have established (modulo some technical details) two significant components of the proof of the Poincaré conjecture: finite time extinction of Ricci flow with surgery (Theorem 4 of Lecture 2), and a -noncollapsing of Ricci flows with surgery (which, except for the surgery part, is Theorem 2 of Lecture 7). Now we come to the heart of the entire argument: the topological and geometric control of the high curvature regions of a Ricci flow, which is absolutely essential in order for one to define surgery on these regions in order to move the flow past singularities. This control is intimately tied to the study of a special type of Ricci flow, the *-solutions* to the Ricci flow equation; we will be able to use compactness arguments (as well as the -noncollapsing results already obtained) to deduce control of high curvature regions of arbitrary Ricci flows from similar control of -solutions. A secondary compactness argument lets us obtain that control of -solutions from control of an even more special type of solution, the *gradient shrinking solitons* that we already encountered in Lecture 8.

[Even once one has this control of high curvature regions, the proof of the Poincaré conjecture is still not finished; there is significant work required to properly define the surgery procedure, and then one has to show that the surgeries do not accumulate in time, and also do not disrupt the various monotonicity formulae that we are using to deduce finite time extinction, -noncollapsing, etc. But the control of high curvature regions is arguably the largest single task one has to establish in the entire proof.]

The next few lectures will be devoted to the analysis of -solutions, culminating in Perelman’s topological and geometric classification (or near-classification) of such solutions (which in particular leads to the *canonical neighbourhood theorem* for these solutions, which we will briefly discuss below). In this lecture we shall formally define the notion of a -solution, and indicate informally why control of such solutions should lead to control of high curvature regions of Ricci flows. We’ll also outline the various types of results that we will prove about -solutions.

Our treatment here is based primarily on the book of Morgan and Tian.


— Definition of a -solution —

We fix a small number (basically the parameter that comes out of the non-collapsing theorem). Here is the formal definition of a -solution:


Definition 1.(-solutions) A-solutionis a Ricci flow which is
-
Ancient, in the sense that t ranges on the interval ;
-
Complete and connected(i.e. (M,g(t)) is complete and connected for every t);
-
Non-negative Riemann curvature, i.e. is positive semidefinite at all points in spacetime;
-
Bounded curvature, thus ;
-
-noncollapsed(see Definition 1 of Lecture 7) at every point in spacetime and at every scale ;
-
Non-flat, i.e. the curvature is non-zero at at least one point in spacetime.
This laundry list of properties arises because they are the properties that we are able to directly establish on limits of rescaled Ricci flows; see below.

**Remark 1. ** If a d-dimensional Riemann manifold is both flat (thus ) and non-collapsed at every scale, then (by Cheeger’s lemma, Theorem 1 from Lecture 7) its injectivity radius is infinite, and by normal coordinates the manifold is isometric to Euclidean space . Thus the non-flat condition is only excluding the *trivial Ricci flow* with the standard (and static) metric. The non-flat condition tells us that the (scalar, say) curvature is positive in at least one point of spacetime, but we will shortly be able to use the strong maximum principle to conclude in fact that the curvature is positive everywhere.
**Remark 2.** In three dimensions, the condition of non-negative RIemann curvature is equivalent to that of non-negative sectional curvature; see the discussion in Lecture 0. In any dimension, the conditions of non-negative bounded Riemann curvature imply that R and are non-negative, and that and . Thus as far as magnitude is concerned, the Riemann and Ricci curvatures of -solutions are controlled by the scalar curvature.
Now we discuss examples (and non-examples) of -solutions.

**Example 1.** Every gradient shrinking soliton or gradient steady soliton (M,g) (see Lecture 8) gives an ancient flow. This flow will be a -solution for sufficiently small if the Einstein manifold (M,g) is complete, connected, non-collapsed at every scale, and is not Euclidean space. For instance, the round sphere with the standard metric is a gradient shrinking solution and will generate a -solution for any and sufficiently small , which we will refer to as the *shrinking round sphere* -solution.
**Exercse 1.** Show that the Cartesian product of two -solutions is again a -solution (with a smaller value of ), as is the Cartesian product of a -solution. Thus for instance the product of the shrinking round 2-sphere and the Euclidean line is a -solution, which we refer to as the *shrinking round 3-cylinder* .
**Example 2.** In one dimension, there are no -solutions, as every manifold is flat; in particular, the 1-sphere (i.e. a circle) is *not* a -solution (it is flat and also collapsed at large scales). In two dimensions, the shrinking round 2-sphere is -solution, as discussed above. We can quotient this by the obvious action to also get a shrinking round projective plane as a -solution. But we shall show in later lectures that if we restrict attention to oriented manifolds, then the shrinking round 2-sphere is the only 2-dimensional -solutions; this result is due to Hamilton, see e.g. Chapter 5 of Chow-Knopf. For instance, the 2-cylinder is not a -solution (it is both flat and collapsed at large scales). The cigar soliton (Example 3 from Lecture 8) also fails to be a -solution due to it being collapsed at large scales.
**Example 3.** In three dimensions, we begin to get significantly more variety amongst -solutions. We have the round shrinking 3-sphere , but also all the quotients of such round spheres by free finite group actions (including the projective space , but with many other examples. We refer to these examples as *round shrinking 3-spherical space forms*. We have also seen the shrinking round cylinder ; there are also finite quotients of this example such as shrinking round projective cylinder , or the quotient of the cylinder by the orientation-preserving free involution . We refer to these examples as the *unoriented and oriented quotients of the shrinking round 3-cylinder* respectively. The oriented quotient can be viewed as a half-cylinder capped off with a punctured (and the whole manifold is in fact homeomorphic to a punctured ).
**Example 4. **One can also imagine perturbations of the shrinking solutions mentioned above. For instance, one could imagine non-round versions of the shrinking or shrinking example, in which the manifold has sectional curvature which is still positive but not constant. We shall informally refer to such solutions as *C-components* (we will define this term formally later, and explain the role of the parameter C). Similarly one could imagine variants of the oriented quotient of the shrinking round cylinder, which are approximately round half-cylinders capped off with what is topologically either a punctured or punctured (i.e. with something homeomorphic to a ball); a 3-dimensional variant of a cigar soliton would fall into this category (such solitons have been constructed by Bryant and by Cao). We informally refer to such solutions as -capped strong -tubes (we will define this term precisely later). One can also consider *doubly -capped strong -tubes*, in which an approximately round finite cylinder is capped off at both ends by either a punctured or punctured ; such manifolds then become homeomorphic to either or . (Note we need to cap off any ends that show up in order to keep the manifold M complete.)
An important theorem of Perelman shows that these examples of -solutions are in fact the only ones:


Theorem 1.(Perelman classification theorem, imprecise version) Every 3-dimensional -solution takes on one of the following forms at time zero (after isometry and rescaling, if necessary):
A shrinking round 3-sphere (or shrinking round spherical space form );
-
A shrinking round 3-cylinder , the quotient , or one of its quotients (either oriented or unoriented);
-
A C-component;
-
A C-capped strong -tube;
-
A doubly C-capped strong -tube.
-
We will make this theorem more precise in later lectures (or if you are impatient, you can read Chapter 9 of Morgan-Tian).

**Remark 3.** At very large scales, Theorem 1 implies that an ancient solution at time zero either looks 0-dimensional (because the manifold was compact, as in the case of a sphere, spherical space form, C-component, or doubly C-capped strong -tube) or 1-dimensional, resembling a line (in the case of the cylinder) or half-line (for C-capped strong -tube). Oversimplifying somewhat, this 0- or 1-dimensionality of the three-dimensional -solutions is the main reason why surgery is even possible; if Ricci flow singularities could look 2-dimensional (such as , or as the product of the cigar soliton and a line) or 3-dimensional (as in ) then it is not clear at all how to define a surgery procedure to excise the singularity. The point is that all the potential candidates for singularity that look 2-dimensional or 3-dimensional at large scales (after rescaling) are either flat or collapsed (or do not have bounded nonnegative curvature), and so are not -solutions. The unoriented quotiented cylinder also causes difficulties with surgery (despite being only one-dimensional at large scales), because it is hard to cap off such a cylinder in a manner which is well-behaved with respect to Ricci flow; however if we assume that the original manifold M contains no embedded copy of (which is for instance the case if the manifold is oriented, and in particular if it is simply connected) then this case does not occur.
**Remark 4.** In four and higher dimensions, things look much worse; consider for instance the product of a shrinking round with the trivial plane . This is a -solution but has a two-dimensional large-scale structure, and so there is no obvious way to remove singularities of this shape by surgery. It may be that in order to have analogues of Perelman’s theory in higher dimensions one has to make much stronger topological or geometric assumptions on the manifold. Note however that four-dimensional Ricci flows with surgery were already considered by Hamilton (with a rather different definition of surgery, however).
The classification theorem lets one understand the geometry of neighbourhoods of any given point in a -solution. Let us make the following imprecise definitions (which, again, will be made precise in later lectures):


Definition 2.(Canonical neighbourhoods, informal version) Let (M,g) be a complete connected 3-manifold, let x be a point in M, and let U be an open neighbourhood of x. We normalise the scalar curvature at x to be 1.
We say that U is an
-
-neckif it is close (in a smooth topology) to a round cylinder , with x well in the middle of of this cylinder;We say that U is a
-
C-componentif U is diffeomorphic to or (in particular, it must be all of M) with sectional curvatures bounded above and below by positive constants, and with diameter comparable to 1.We say that U is
-
-roundif it is close (in a smooth topology) to a round sphere or spherical space form (i.e. it is close to a constant curvature manifold).We say that U is a
-
-capif it consists of an -neck together with a cap at one end, where the cap is homeomorphic to either an open 3-ball or a punctured and obeys similar bounds as a C-component, and that x is contained inside the cap. (For technical reasons one also needs some derivative bounds on curvature, but we omit them here.)We say that U is a
-
canonical neighbourhoodof x if it is one of the above four types.When the scalar curvature is some other positive number than 1, we can generalise the above definition by rescaling the metric to have curvature 1.

Using Theorem 1 (and defining all terms precisely), one can easily show the following important statement:

Corollary 1(Canonical neighbourhood theorem for -solitons, informal version) Every point in a 3-dimensional -solution that does not contain an embedded copy of with trivial normal bundle is contained in a canonical neighbourhood.
The next few lectures will be devoted to establishing precise versions of Theorem 1, Definition 2, and Corollary 1.

— High curvature regions of Ricci flows —

Corollary 1 is an assertion about -solutions only, but it implies an important property about more general Ricci flows:

Theorem 2.(Canonical neighbourhood for Ricci flows, informal version) Let be a Ricci flow of compact 3-manifolds on a time interval , without any embedded copy of with trivial normal bundle. Then every point with sufficiently large scalar curvature is contained in a canonical neighbourhood.
(Actually, as with many other components of this proof, we actually need a generalisation of this result for Ricci flow with surgery, but we will address this (non-trivial) complication later.)

The importance of this theorem lies in the fact that all the singular regions that need surgery will have large scalar curvature, and Theorem 2 provides the crucial topological and geometric control in order to perform surgery on these regions. (This is a significant oversimplification, as one has to also study certain “horns” that appear at the singular time in order to find a particularly good place to perform surgery, but we will postpone discussion of this major additional issue later in this course.)

Theorem 2 is deduced from Corollary 1 and a significant number of additional arguments. The strategy is to use a compactness-and-contradiction argument. As a very crude first approximation, the proof goes as follows:

Suppose for contradiction that Theorem 2 failed. Then one could find a sequence of points with which were not contained in canonical neighbourhoods.
-
M, being compact, has finitely many components; by restricting attention to a subsequence of points if necessary, we can take M to be connected.
-
On any compact time interval , the scalar curvature is necessarily bounded, and thus . As a consequence, if we define the rescaled Ricci flows , where is the natural length scale associated to the scalar curvature at , then these flows will become increasingly ancient. Note that in the limit (which we will not define rigorously yet, but think of a pointed Gromov-Hausdorff limit for now), the increasingly large manifolds may cease to be compact, but will remain complete.
-
Because of the Hamilton-Ivey pinching phenomenon (Theorem 1 from Lecture 3), we expect the rescaled flows to have non-negative Ricci curvature in the limit (and hence non-negative Riemann curvature also, as we are in three dimensions).
-
If we can pick the points suitably (so that the scalar curvature is larger than or comparable to the scalar curvatures at other nearby points), then we should be able to ensure that the rescaled flows have bounded curvature in the limit.
-
Since -noncollapsing is invariant under rescaling, the non-collapsing theorem (Theorem 2 of Lecture 7) should ensure that the rescaled flows remain -noncollapsed in the limit.
-
Since the rescaled scalar curvature at the base point of is equal to 1 by construction, any limiting flow will be non-flat.
-
Various compactness theorems (of Gromov, Hamilton, and Perelman) exploiting the non-collapsed, bounded curvature, and parabolic nature of the rescaled Ricci flows now allows one to extract a limiting flow . This limit is initially in a fairly weak sense, but one can use parabolic theory to upgrade the convergence to quite a strong (and smooth) convergence. In particular, the limit of the Ricci flows will remain a Ricci flow.
-
Applying 2-8, we see that the limiting flow is a -solution.
-
Applying Corollary 1, we conclude that every point in the limiting flow lies inside a canonical neighbourhood. Using the strong nature of the convergence (and the scale-invariant nature of canonical neighbourhoods), we deduce that the points also lie in canonical neighbourhoods for sufficiently large n, a contradiction.
-
There are some non-trivial technical difficulties in executing the above scheme, especially in Step 5 and Step 8. Step 8 will require some compactness theorems for -solutions which we will deduce in later lectures. For Step 5, the problem is that the points that we are trying to place inside canonical neighbourhoods have large curvature, but they may be adjacent to other points of significantly higher curvature, so that the limiting flow ends up having unbounded curvature. To get around this, Perelman established Theorem 2 by a downwards induction argument on the curvature, first establishing the result for extremely high curvature, then for slightly less extreme curvature, and so forth. The point is that with such an induction hypothesis, any potentially bad adjacent points of really high curvature will be safely tucked away in a canonical neighbourhood of high curvature, which in turn is connected to another canonical neighbourhood of high curvature, and so forth; some basic topological and geometric analysis then eventually lets us conclude that this bad point must in fact be quite far from the base point (much further away than the natural length scale , in particular), so that it does not show up in the limiting flow . We will discuss these issues in more detail in later lectures.

— Benchmarks in controlling -solutions —

As mentioned earlier, the next few lectures will be focused on controlling -solutions. It turns out that the various properties in Definition 1 interact very well with each other, and give remarkably precise control on these solutions. In this section we state (without proofs) some of the results we will establish concerning such solutions.


Proposition 1.(Consequences of Hamilton’s Harnack inequality) Let be a -solution. Then is a non-decreasing function of time. Furthermore, for any , we have the pointwise inequalities(1)

and

(2)

on , where of course is the backwards time variable.

These inequalities follow from an important Harnack inequality of Hamilton (also related to earlier work of Li and Yau) that we will discuss in the next lecture. These results rely primarily on the ancient and non-negatively curved nature of -solutions, as well as the Ricci flow equation of course.

Now one can handle the two-dimensional case:

Proposition 2.(Classification of 2-dimensional -solutions) The only two-dimensional -solutions are the round shrinking 2-spheres.
This proposition relies on first studying a certain asymptotic limit of the -solution, known as the asymptotic soliton, to be defined later. One shows that this asymptotic limit is a round shrinking 2-sphere, which implies that the original -solution is asymptotically a round shrinking 2-sphere. One can then invoke Hamilton’s rounding theorem to finish the claim.

Turning now to three dimensions, the first important result that the curvature R decays slower at infinity than what scaling naively predicts.

Proposition 3.(Asymptotic curvature) Let be a 3-dimensional solution which is not compact. Then for any time and any base point , we have .
The proof of Proposition 3 is based on another compactness-and-contradiction argument which also heavily exploits some splitting theorems in Riemannian geometry, as well as the soul theorem.

The increasing curvature at infinity can be used to show that the volume does not grow as fast at infinity as scaling predicts:


Proposition 4.(Asymptotic volume collapse) Let be a 3-dimensional solution which is not compact. Then for any time and any base point , we have .
Note that Proposition 4 does not contradict the non-collapsed nature of the flow, since one does not expect bounded normalised curvature at extremely large scales. Proposition 4 morally follows from Bishop-Gromov comparison geometry theory, but its proof in fact uses yet another compactness-and-contradiction argument combined with splitting theory.

An important variant of Proposition 4 and Proposition 3 (and yet another compactness-and-contradiction argument) states that on any ball at time zero on which the volume is large (e.g. larger than for some ), one has bounded normalised curvature, thus on this ball. This fact helps us deduce

Theorem 3.(Perelman compactness theorem, informal version) The space of all pointed -solutions (allowing to range over the positive real numbers) is compact (in a suitable topology) after normalising the scalar curvature at the base point to be 1.
One corollary of this compactness is that there is in fact a universal such that every -solution is a -solution. (Indeed, the proof of this universality is one of the key steps in the proof of the above theorem.) This theorem is proven by establishing some uniform curvature bounds on -solutions which come from the previous volume analysis.

The proof of Theorem 1 (and thus Corollary 1) follows from this compactness once one can classify the asymptotic solitons mentioned earlier. This task in turn requires many of the techniques already mentioned, together with some variational analysis of the gradient curves of the potential function f that controls the geometry of the soliton.
""",
    content=r"""In previous lectures, we have established (modulo some technical details) two significant components of the proof of the Poincaré conjecture: finite time extinction of Ricci flow with surgery (Theorem 4 of Lecture 2), and a $\kappa$ -noncollapsing of Ricci flows with surgery (which, except for the surgery part, is Theorem 2 of Lecture 7). Now we come to the heart of the entire argument: the topological and geometric control of the high curvature regions of a Ricci flow, which is absolutely essential in order for one to define surgery on these regions in order to move the flow past singularities. This control is intimately tied to the study of a special type of Ricci flow, the $\kappa$ -solutions to the Ricci flow equation; we will be able to use compactness arguments (as well as the $\kappa$ -noncollapsing results already obtained) to deduce control of high curvature regions of arbitrary Ricci flows from similar control of $\kappa$ -solutions. A secondary compactness argument lets us obtain that control of $\kappa$ -solutions from control of an even more special type of solution, the gradient shrinking solitons that we already encountered in Lecture 8.

[Even once one has this control of high curvature regions, the proof of the Poincaré conjecture is still not finished; there is significant work required to properly define the surgery procedure, and then one has to show that the surgeries do not accumulate in time, and also do not disrupt the various monotonicity formulae that we are using to deduce finite time extinction, $\kappa$ -noncollapsing, etc. But the control of high curvature regions is arguably the largest single task one has to establish in the entire proof.]

The next few lectures will be devoted to the analysis of $\kappa$ -solutions, culminating in Perelman’s topological and geometric classification (or near-classification) of such solutions (which in particular leads to the canonical neighbourhood theorem for these solutions, which we will briefly discuss below). In this lecture we shall formally define the notion of a $\kappa$ -solution, and indicate informally why control of such solutions should lead to control of high curvature regions of Ricci flows. We’ll also outline the various types of results that we will prove about $\kappa$ -solutions.

Our treatment here is based primarily on the book of Morgan and Tian.

— Definition of a $\kappa$ -solution —

We fix a small number $\kappa > 0$ (basically the parameter that comes out of the non-collapsing theorem). Here is the formal definition of a $\kappa$ -solution:

Definition 1. ( $\kappa$ -solutions) A $\kappa$ -solution is a Ricci flow $t \mapsto (M,g(t))$ which is

1. Ancient , in the sense that t ranges on the interval $(-\infty,0]$ ;
2. Complete and connected (i.e. (M,g(t)) is complete and connected for every t);
3. Non-negative Riemann curvature , i.e. $\hbox{Riem}: \bigwedge^2 TM \to \bigwedge^2 TM$ is positive semidefinite at all points in spacetime;
4. Bounded curvature , thus $\sup_{(t,x) \in (-\infty,0] \times M} |\hbox{Riem}|_g < +\infty$ ;
5. $\kappa$ -noncollapsed (see Definition 1 of Lecture 7 ) at every point $(t_0,x_0)$ in spacetime and at every scale $r_0 > 0$ ;
6. Non-flat , i.e. the curvature is non-zero at at least one point in spacetime.

This laundry list of properties arises because they are the properties that we are able to directly establish on limits of rescaled Ricci flows; see below.

Remark 1. If a d-dimensional Riemann manifold is both flat (thus $\hbox{Riem}=0$ ) and non-collapsed at every scale, then (by Cheeger’s lemma, Theorem 1 from Lecture 7) its injectivity radius is infinite, and by normal coordinates the manifold is isometric to Euclidean space ${\Bbb R}^d$ . Thus the non-flat condition is only excluding the trivial Ricci flow $M = {\Bbb R}^d$ with the standard (and static) metric. The non-flat condition tells us that the (scalar, say) curvature is positive in at least one point of spacetime, but we will shortly be able to use the strong maximum principle to conclude in fact that the curvature is positive everywhere. $\diamond$

Remark 2. In three dimensions, the condition of non-negative RIemann curvature is equivalent to that of non-negative sectional curvature; see the discussion in Lecture 0. In any dimension, the conditions of non-negative bounded Riemann curvature imply that R and $\hbox{Ric}$ are non-negative, and that $|\hbox{Riem}|_g, |\hbox{Ric}|_g = O(R)$ and $R = O_d(1)$ . Thus as far as magnitude is concerned, the Riemann and Ricci curvatures of $\kappa$ -solutions are controlled by the scalar curvature. $\diamond$

Now we discuss examples (and non-examples) of $\kappa$ -solutions.

Example 1. Every gradient shrinking soliton or gradient steady soliton (M,g) (see Lecture 8) gives an ancient flow. This flow will be a $\kappa$ -solution for sufficiently small $\kappa$ if the Einstein manifold (M,g) is complete, connected, non-collapsed at every scale, and is not Euclidean space. For instance, the round sphere $S^d$ with the standard metric is a gradient shrinking solution and will generate a $\kappa$ -solution for any $d \geq 2$ and sufficiently small $\kappa > 0$ , which we will refer to as the shrinking round sphere $\kappa$ -solution. $\diamond$

Exercse 1. Show that the Cartesian product of two $\kappa$ -solutions is again a $\kappa$ -solution (with a smaller value of $\kappa$ ), as is the Cartesian product of a $\kappa$ -solution. Thus for instance the product $S^2 \times {\Bbb R}$ of the shrinking round 2-sphere and the Euclidean line is a $\kappa$ -solution, which we refer to as the shrinking round 3-cylinder $S^2 \times {\Bbb R}$ . $\diamond$

Example 2. In one dimension, there are no $\kappa$ -solutions, as every manifold is flat; in particular, the 1-sphere (i.e. a circle) is not a $\kappa$ -solution (it is flat and also collapsed at large scales). In two dimensions, the shrinking round 2-sphere $S^2$ is $\kappa$ -solution, as discussed above. We can quotient this by the obvious ${\Bbb Z}/2$ action to also get a shrinking round projective plane $\Bbb{RP}^2$ as a $\kappa$ -solution. But we shall show in later lectures that if we restrict attention to oriented manifolds, then the shrinking round 2-sphere is the only 2-dimensional $\kappa$ -solutions; this result is due to Hamilton, see e.g. Chapter 5 of Chow-Knopf. For instance, the 2-cylinder $S^1 \times {\Bbb R}$ is not a $\kappa$ -solution (it is both flat and collapsed at large scales). The cigar soliton (Example 3 from Lecture 8) also fails to be a $\kappa$ -solution due to it being collapsed at large scales. $\diamond$

Example 3. In three dimensions, we begin to get significantly more variety amongst $\kappa$ -solutions. We have the round shrinking 3-sphere $S^3$ , but also all the quotients $S^3/\Gamma$ of such round spheres by free finite group actions (including the projective space ${\Bbb RP}^3$ , but with many other examples. We refer to these examples as round shrinking 3-spherical space forms. We have also seen the shrinking round cylinder $S^2 \times {\Bbb R}$ ; there are also finite quotients of this example such as shrinking round projective cylinder $\Bbb{RP}^2 \times {\Bbb R}$ , or the quotient of the cylinder by the orientation-preserving free involution $(\omega,z) \mapsto (-\omega,-z)$ . We refer to these examples as the unoriented and oriented quotients of the shrinking round 3-cylinder respectively. The oriented quotient can be viewed as a half-cylinder $S^2 \times [1,+\infty)$ capped off with a punctured $\Bbb{RP}^3$ (and the whole manifold is in fact homeomorphic to a punctured $\Bbb{RP}^3$ ). $\diamond$

Example 4. One can also imagine perturbations of the shrinking solutions mentioned above. For instance, one could imagine non-round versions of the shrinking $S^2$ or shrinking ${\Bbb RP}^3$ example, in which the manifold has sectional curvature which is still positive but not constant. We shall informally refer to such solutions as C-components (we will define this term formally later, and explain the role of the parameter C). Similarly one could imagine variants of the oriented quotient of the shrinking round cylinder, which are approximately round half-cylinders $S^2 \times [1,+\infty)$ capped off with what is topologically either a punctured $\Bbb{RP}^3$ or punctured $S^3$ (i.e. with something homeomorphic to a ball); a 3-dimensional variant of a cigar soliton would fall into this category (such solitons have been constructed by Bryant and by Cao). We informally refer to such solutions as $C$ -capped strong $\varepsilon$ -tubes (we will define this term precisely later). One can also consider doubly $C$ -capped strong $\varepsilon$ -tubes, in which an approximately round finite cylinder $S^2 \times [-T,T]$ is capped off at both ends by either a punctured $\Bbb{RP}^3$ or punctured $S^3$ ; such manifolds then become homeomorphic to either $S^3$ or ${\Bbb RP}^3$ . (Note we need to cap off any ends that show up in order to keep the manifold M complete.) $\diamond$

An important theorem of Perelman shows that these examples of $\kappa$ -solutions are in fact the only ones:

Theorem 1. (Perelman classification theorem, imprecise version) Every 3-dimensional $\kappa$ -solution takes on one of the following forms at time zero (after isometry and rescaling, if necessary):

1. A shrinking round 3-sphere $S^3$ (or shrinking round spherical space form $S^3/\Gamma$ );
2. A shrinking round 3-cylinder $S^2 \times {\Bbb R}$ , the quotient $\Bbb{RP}^2 \times {\Bbb R}$ , or one of its quotients (either oriented or unoriented);
3. A C-component;
4. A C-capped strong $\varepsilon$ -tube;
5. A doubly C-capped strong $\varepsilon$ -tube.

We will make this theorem more precise in later lectures (or if you are impatient, you can read Chapter 9 of Morgan-Tian).

Remark 3. At very large scales, Theorem 1 implies that an ancient solution at time zero either looks 0-dimensional (because the manifold was compact, as in the case of a sphere, spherical space form, C-component, or doubly C-capped strong $\varepsilon$ -tube) or 1-dimensional, resembling a line (in the case of the cylinder) or half-line (for C-capped strong $\varepsilon$ -tube). Oversimplifying somewhat, this 0- or 1-dimensionality of the three-dimensional $\kappa$ -solutions is the main reason why surgery is even possible; if Ricci flow singularities could look 2-dimensional (such as $S^1 \times {\Bbb R}^2$ , or as the product of the cigar soliton and a line) or 3-dimensional (as in ${\Bbb R}^3$ ) then it is not clear at all how to define a surgery procedure to excise the singularity. The point is that all the potential candidates for singularity that look 2-dimensional or 3-dimensional at large scales (after rescaling) are either flat or collapsed (or do not have bounded nonnegative curvature), and so are not $\kappa$ -solutions. The unoriented quotiented cylinder $\Bbb{RP}^2 \times {\Bbb R}$ also causes difficulties with surgery (despite being only one-dimensional at large scales), because it is hard to cap off such a cylinder in a manner which is well-behaved with respect to Ricci flow; however if we assume that the original manifold M contains no embedded copy of $\Bbb{RP}^2 \times {\Bbb R}$ (which is for instance the case if the manifold is oriented, and in particular if it is simply connected) then this case does not occur. $\diamond$

Remark 4. In four and higher dimensions, things look much worse; consider for instance the product of a shrinking round $S^2$ with the trivial plane ${\Bbb R}^2$ . This is a $\kappa$ -solution but has a two-dimensional large-scale structure, and so there is no obvious way to remove singularities of this shape by surgery. It may be that in order to have analogues of Perelman’s theory in higher dimensions one has to make much stronger topological or geometric assumptions on the manifold. Note however that four-dimensional Ricci flows with surgery were already considered by Hamilton (with a rather different definition of surgery, however).

The classification theorem lets one understand the geometry of neighbourhoods of any given point in a $\kappa$ -solution. Let us make the following imprecise definitions (which, again, will be made precise in later lectures):

Definition 2. (Canonical neighbourhoods, informal version) Let (M,g) be a complete connected 3-manifold, let x be a point in M, and let U be an open neighbourhood of x. We normalise the scalar curvature at x to be 1.

1. We say that U is an $\varepsilon$ -neck if it is close (in a smooth topology) to a round cylinder $S^2 \times (-R,R)$ , with x well in the middle of of this cylinder;
2. We say that U is a C-component if U is diffeomorphic to $S^3$ or $\Bbb{RP}^3$ (in particular, it must be all of M) with sectional curvatures bounded above and below by positive constants, and with diameter comparable to 1.
3. We say that U is $\varepsilon$ -round if it is close (in a smooth topology) to a round sphere $S^3$ or spherical space form $S^3/\Gamma$ (i.e. it is close to a constant curvature manifold).
4. We say that U is a $(C,\varepsilon)$ -cap if it consists of an $\varepsilon$ -neck together with a cap at one end, where the cap is homeomorphic to either an open 3-ball or a punctured ${\Bbb RP}^3$ and obeys similar bounds as a C-component, and that x is contained inside the cap. (For technical reasons one also needs some derivative bounds on curvature, but we omit them here.)
5. We say that U is a canonical neighbourhood of x if it is one of the above four types.

When the scalar curvature is some other positive number than 1, we can generalise the above definition by rescaling the metric to have curvature 1.

Using Theorem 1 (and defining all terms precisely), one can easily show the following important statement:

Corollary 1 (Canonical neighbourhood theorem for $\kappa$ -solitons, informal version) Every point in a 3-dimensional $\kappa$ -solution that does not contain an embedded copy of $\Bbb{RP}^2$ with trivial normal bundle is contained in a canonical neighbourhood.

The next few lectures will be devoted to establishing precise versions of Theorem 1, Definition 2, and Corollary 1.

— High curvature regions of Ricci flows —

Corollary 1 is an assertion about $\kappa$ -solutions only, but it implies an important property about more general Ricci flows:

Theorem 2. (Canonical neighbourhood for Ricci flows, informal version) Let $t \mapsto (M,g)$ be a Ricci flow of compact 3-manifolds on a time interval ${}[0,T)$ , without any embedded copy of $\Bbb{RP}^2$ with trivial normal bundle. Then every point $(t,x) \in [0,T) \times M$ with sufficiently large scalar curvature is contained in a canonical neighbourhood.

(Actually, as with many other components of this proof, we actually need a generalisation of this result for Ricci flow with surgery, but we will address this (non-trivial) complication later.)

The importance of this theorem lies in the fact that all the singular regions that need surgery will have large scalar curvature, and Theorem 2 provides the crucial topological and geometric control in order to perform surgery on these regions. (This is a significant oversimplification, as one has to also study certain “horns” that appear at the singular time in order to find a particularly good place to perform surgery, but we will postpone discussion of this major additional issue later in this course.)

Theorem 2 is deduced from Corollary 1 and a significant number of additional arguments. The strategy is to use a compactness-and-contradiction argument. As a very crude first approximation, the proof goes as follows:

1. Suppose for contradiction that Theorem 2 failed. Then one could find a sequence $(t_n,x_n) \in [0,T) \times M$ of points with $R(t_n,x_n) \to +\infty$ which were not contained in canonical neighbourhoods.
2. M, being compact, has finitely many components; by restricting attention to a subsequence of points if necessary, we can take M to be connected.
3. On any compact time interval ${}[0,t] \times M$ , the scalar curvature is necessarily bounded, and thus $t_n \to T$ . As a consequence, if we define the rescaled Ricci flows $g^{(n)}(t) = \frac{1}{L_n^2} g( t_n + L_n^2 t )$ , where $L_n := R(t_n,x_n)^{-1/2}$ is the natural length scale associated to the scalar curvature at $(t_n,x_n)$ , then these flows will become increasingly ancient. Note that in the limit (which we will not define rigorously yet, but think of a pointed Gromov-Hausdorff limit for now), the increasingly large manifolds $(M,g^{(n)}(t))$ may cease to be compact, but will remain complete.
4. Because of the Hamilton-Ivey pinching phenomenon (Theorem 1 from Lecture 3 ), we expect the rescaled flows $t \mapsto (M, g^{(n)}(t))$ to have non-negative Ricci curvature in the limit (and hence non-negative Riemann curvature also, as we are in three dimensions).
5. If we can pick the points $(t_n,x_n)$ suitably (so that the scalar curvature $R(t_n,x_n)$ is larger than or comparable to the scalar curvatures at other nearby points), then we should be able to ensure that the rescaled flows $t \mapsto (M, g^{(n)}(t))$ have bounded curvature in the limit.
6. Since $\kappa$ -noncollapsing is invariant under rescaling, the non-collapsing theorem (Theorem 2 of Lecture 7 ) should ensure that the rescaled flows remain $\kappa$ -noncollapsed in the limit.
7. Since the rescaled scalar curvature at the base point $x_n$ of $(M,g^{(n)})$ is equal to 1 by construction, any limiting flow will be non-flat.
8. Various compactness theorems (of Gromov, Hamilton, and Perelman) exploiting the non-collapsed, bounded curvature, and parabolic nature of the rescaled Ricci flows now allows one to extract a limiting flow $(M^{(\infty)}, g^{(\infty)})$ . This limit is initially in a fairly weak sense, but one can use parabolic theory to upgrade the convergence to quite a strong (and smooth) convergence. In particular, the limit of the Ricci flows will remain a Ricci flow.
9. Applying 2-8, we see that the limiting flow $(M^{(\infty)}, g^{(\infty)})$ is a $\kappa$ -solution.
10. Applying Corollary 1, we conclude that every point in the limiting flow lies inside a canonical neighbourhood. Using the strong nature of the convergence (and the scale-invariant nature of canonical neighbourhoods), we deduce that the points $(t_n,x_n)$ also lie in canonical neighbourhoods for sufficiently large n, a contradiction.

There are some non-trivial technical difficulties in executing the above scheme, especially in Step 5 and Step 8. Step 8 will require some compactness theorems for $\kappa$ -solutions which we will deduce in later lectures. For Step 5, the problem is that the points $(t_n,x_n)$ that we are trying to place inside canonical neighbourhoods have large curvature, but they may be adjacent to other points of significantly higher curvature, so that the limiting flow $(M^{(\infty)}, g^{(\infty)})$ ends up having unbounded curvature. To get around this, Perelman established Theorem 2 by a downwards induction argument on the curvature, first establishing the result for extremely high curvature, then for slightly less extreme curvature, and so forth. The point is that with such an induction hypothesis, any potentially bad adjacent points of really high curvature will be safely tucked away in a canonical neighbourhood of high curvature, which in turn is connected to another canonical neighbourhood of high curvature, and so forth; some basic topological and geometric analysis then eventually lets us conclude that this bad point must in fact be quite far from the base point $(t_n,x_n)$ (much further away than the natural length scale $L_n$ , in particular), so that it does not show up in the limiting flow $(M^{(\infty)}, g^{(\infty)})$ . We will discuss these issues in more detail in later lectures.

— Benchmarks in controlling $\kappa$ -solutions —

As mentioned earlier, the next few lectures will be focused on controlling $\kappa$ -solutions. It turns out that the various properties in Definition 1 interact very well with each other, and give remarkably precise control on these solutions. In this section we state (without proofs) some of the results we will establish concerning such solutions.

Proposition 1. (Consequences of Hamilton’s Harnack inequality) Let $t \mapsto (M,g(t))$ be a $\kappa$ -solution. Then $R(t,x)$ is a non-decreasing function of time. Furthermore, for any $(t_0,x_0) \in (-\infty,0] \times M$ , we have the pointwise inequalities

$\displaystyle |\nabla l_{(t_0,x_0)}|^2 + R \leq \frac{3 l_{(t_0,x_0)}}{\tau}$ (1)

and

$\displaystyle -2 \frac{l_{(t_0,x_0)}}{\tau} \leq \frac{\partial l_{(t_0,x_0)}}{\partial \tau} \leq \frac{l_{(t_0,x_0)}}{\tau}$ (2)

on $(-\infty,t_0) \times M$ , where of course $\tau := t_0 - t$ is the backwards time variable.

These inequalities follow from an important Harnack inequality of Hamilton (also related to earlier work of Li and Yau) that we will discuss in the next lecture. These results rely primarily on the ancient and non-negatively curved nature of $\kappa$ -solutions, as well as the Ricci flow equation $\dot g = -2 \hbox{Ric}$ of course.

Now one can handle the two-dimensional case:

Proposition 2.(Classification of 2-dimensional $\kappa$ -solutions) The only two-dimensional $\kappa$ -solutions are the round shrinking 2-spheres.

This proposition relies on first studying a certain asymptotic limit of the $\kappa$ -solution, known as the asymptotic soliton, to be defined later. One shows that this asymptotic limit is a round shrinking 2-sphere, which implies that the original $\kappa$ -solution is asymptotically a round shrinking 2-sphere. One can then invoke Hamilton’s rounding theorem to finish the claim.

Turning now to three dimensions, the first important result that the curvature R decays slower at infinity than what scaling naively predicts.

Proposition 3. (Asymptotic curvature) Let $t \mapsto (M,g(t))$ be a 3-dimensional $\kappa$ solution which is not compact. Then for any time $t \in (-\infty,0)$ and any base point $p \in M$ , we have $\limsup_{x \to \infty} R(t,x) d_{g(t)}(x,p)^2 = +\infty$ .

The proof of Proposition 3 is based on another compactness-and-contradiction argument which also heavily exploits some splitting theorems in Riemannian geometry, as well as the soul theorem.

The increasing curvature at infinity can be used to show that the volume does not grow as fast at infinity as scaling predicts:

Proposition 4. (Asymptotic volume collapse) Let $t \mapsto (M,g(t))$ be a 3-dimensional $\kappa$ solution which is not compact. Then for any time $t \in (-\infty,0)$ and any base point $p \in M$ , we have $\limsup_{r \to +\infty} \hbox{Vol}_{g(t)}( B_{g(t)})(p,r) ) / r^3 = 0$ .

Note that Proposition 4 does not contradict the non-collapsed nature of the flow, since one does not expect bounded normalised curvature at extremely large scales. Proposition 4 morally follows from Bishop-Gromov comparison geometry theory, but its proof in fact uses yet another compactness-and-contradiction argument combined with splitting theory.

An important variant of Proposition 4 and Proposition 3 (and yet another compactness-and-contradiction argument) states that on any ball $B_{g(0)}(p,r)$ at time zero on which the volume is large (e.g. larger than $\nu r^3$ for some $\nu > 0$ ), one has bounded normalised curvature, thus $R = O_\nu( 1 / r^2 )$ on this ball. This fact helps us deduce

Theorem 3. (Perelman compactness theorem, informal version) The space of all pointed $\kappa$ -solutions (allowing $\kappa > 0$ to range over the positive real numbers) is compact (in a suitable topology) after normalising the scalar curvature at the base point to be 1.

One corollary of this compactness is that there is in fact a universal $\kappa_0 > 0$ such that every $\kappa$ -solution is a $\kappa_0$ -solution. (Indeed, the proof of this universality is one of the key steps in the proof of the above theorem.) This theorem is proven by establishing some uniform curvature bounds on $\kappa$ -solutions which come from the previous volume analysis.

The proof of Theorem 1 (and thus Corollary 1) follows from this compactness once one can classify the asymptotic solitons mentioned earlier. This task in turn requires many of the techniques already mentioned, together with some variational analysis of the gradient curves of the potential function f that controls the geometry of the soliton.
    """,
    raw_data={
        "language": "en",  # 指定语言为英文
    }
)


def run_comparison(data: Data, description: str):
    """运行对比评估"""
    print(f"\n{'=' * 60}")
    print(f"测试场景: {description}")
    print(f"{'=' * 60}\n")

    # 执行评估
    result = evaluator.eval(data)

    # 打印结果
    # print(f"评估结果类型: {result.type}")
    # print(f"判断名称: {result.name}")
    print(f"是否存在问题: {result.status}")
    print(f"评估结果类型: {result.label}")
    print(f"\n推理过程:\n{result.reason}")
    print(f"\n{'=' * 60}\n")


if __name__ == "__main__":
    # 测试中文场景
    run_comparison(example_data_en, "对比两种HTML提取工具")

    # 测试英文场景
    # run_comparison(example_data_en, "英文网页 - 对比两种HTML提取工具")

    print("\n说明 (V3 label 与 Data 字段一致):")
    print("- score=1 → PROMPT_BETTER：Data.prompt 侧抽取质量更好")
    print("- score=2 → CONTENT_BETTER：Data.content 侧更好")
    print("- score=0 → EXTRACTION_EQUAL：两者相当")
